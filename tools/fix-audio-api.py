#!/usr/bin/env python3
"""修 OH 内核补丁里的 ASoC API 不匹配（sound/soc/rockchip-oh/rockchip_i2s.c）。

问题：该文件用了 `snd_soc_dai_driver.probe`，这个字段是 Linux 6.7 才加入的，
6.6 的结构体里没有 -> `error: field designator 'probe' does not refer to any field`。

之前一直没暴露，因为 rk3568 的 defconfig 把 CONFIG_SOUND/CONFIG_SND 总开关关着，
sound/soc/rockchip-oh/ 整个目录根本没参与编译。

改法：probe 里做的唯一必要动作是 snd_soc_dai_init_dma_data（初始化 DMA 数据），
把它挪到 .startup 回调（6.6 的标准位置），再删掉 .probe 指示器。

用法：fix-audio-api.py <kernel_src_tmp_path>
幂等：重复执行不会重复插入。
"""
import pathlib
import sys

MARK = "6.6 的 snd_soc_dai_driver 没有 .probe"

OLD_ANCHOR = """	int stream = substream->stream;

	if (i2s->substreams[stream])
		return -EBUSY;
"""

NEW_BODY = """	int stream = substream->stream;

	/* 6.6 的 snd_soc_dai_driver 没有 .probe 回调（6.7+ 才有），
	 * 把原 rockchip_i2s_dai_probe 里的 dma data 初始化挪到 startup。 */
	snd_soc_dai_init_dma_data(dai,
		i2s->has_playback ? &i2s->playback_dma_data : NULL,
		i2s->has_capture  ? &i2s->capture_dma_data  : NULL);

	if (i2s->substreams[stream])
		return -EBUSY;
"""


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    p = root / "sound/soc/rockchip-oh/rockchip_i2s.c"
    if not p.is_file():
        print("[audio-api] 找不到 %s，跳过" % p)
        return 0

    s = p.read_text()
    orig = s

    # 1) startup 里补 dma data 初始化
    if MARK in s:
        print("[audio-api] startup 已打过补丁")
    elif s.count(OLD_ANCHOR) == 1:
        s = s.replace(OLD_ANCHOR, NEW_BODY, 1)
        print("[audio-api] startup 注入 snd_soc_dai_init_dma_data")
    else:
        print("[audio-api] !! startup 锚点匹配 %d 次，需人工检查" % s.count(OLD_ANCHOR))
        return 1

    # 2) 删掉 6.6 不存在的 .probe 指示器
    probe_line = "\t.probe = rockchip_i2s_dai_probe,\n"
    if probe_line in s:
        s = s.replace(probe_line, "", 1)
        print("[audio-api] 删除 .probe 指示器")
    else:
        print("[audio-api] .probe 指示器已不存在")

    # 3) 函数保留但改成 maybe_unused，避免 -Wunused-function
    sig = "static int rockchip_i2s_dai_probe(struct snd_soc_dai *dai)"
    if sig in s:
        s = s.replace(sig, "static int __maybe_unused rockchip_i2s_dai_probe(struct snd_soc_dai *dai)", 1)
        print("[audio-api] rockchip_i2s_dai_probe 标记 __maybe_unused")

    if s != orig:
        p.write_text(s)
        print("[audio-api] 已写回 %s" % p)
    else:
        print("[audio-api] 无变化")
    return 0


if __name__ == "__main__":
    sys.exit(main())
