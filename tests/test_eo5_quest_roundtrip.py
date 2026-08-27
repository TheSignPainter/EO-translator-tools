# -*- coding: utf-8 -*-
"""EO5 转换/逆转换函数单元测试。

覆盖 EO5/MBM/Hontai/EVENT/QUEST 下所有 XML 文件的所有 <source> 文本，验证：

1. 转换（parse_single_entry）：
   - 所有 source 均可转换；
   - voice（{f81b}...{0000}）必须全部转为 [[voice: 角色名 hash]] 占位符，
     不允许残留未转换的 {f81b}；
   - 占位符中的 hash 必须存在于已分发的 EO5/voice_hash_table.json
     （模块加载后的 VOICE_HASH_TABLE），且数量与原文 voice 控制字符一致。
2. 逆转换（parse_single_entry_revert）：revert 后必须与转换前文本完全一致。

运行（仓库根目录）：
    python -m unittest discover -s tests -v
"""

import json
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from EO5.single_parser import (  # noqa: E402
    VOICE_HASH_FILE,
    VOICE_HASH_TABLE,
    VOICE_PLACEHOLDER_RE,
    parse_single_entry,
    parse_single_entry_revert,
)

QUEST_DIR = ROOT / "EO5" / "MBM" / "Hontai" / "EVENT" / "QUEST"

# 大小写不敏感的 voice 控制字符匹配（统计与残留检查用）
F81B_RE_CI = re.compile(
    r"\{f81b\}"
    r"(?:\{(?!0000\})[0-9a-fA-F]{4}\})*"
    r"\{0000\}",
    re.IGNORECASE,
)


def iter_quest_sources():
    """遍历 QUEST 目录下所有 XML，产出 (文件名, entry id, source 文本)。"""
    for xml_path in sorted(QUEST_DIR.glob("*.xml")):
        tree = ET.parse(xml_path)
        for entry in tree.getroot():
            if entry.tag != "entry":
                continue
            src = entry.find("source")
            if src is None or src.text is None:
                continue
            yield xml_path.name, entry.attrib.get("id"), src.text


class EO5QuestRoundTripTests(unittest.TestCase):
    """EO5 QUEST 全部 <source> 的转换 / 逆转换往返测试。"""

    @classmethod
    def setUpClass(cls):
        cls.sources = list(iter_quest_sources())
        cls.files = sorted({fname for fname, _, _ in cls.sources})

    def test_quest_directory_contains_sources(self):
        self.assertGreater(len(self.files), 0, "QUEST 目录下没有可测试的 XML 文件")
        self.assertGreater(len(self.sources), 0, "QUEST 文件里没有 <source> 文本")

    def test_voice_hash_table_is_loaded_from_persisted_json(self):
        """voice 还原依赖的 hash 表必须来自已存在的 voice_hash_table.json。"""
        self.assertTrue(
            Path(VOICE_HASH_FILE).is_file(),
            f"voice hash 表文件不存在: {VOICE_HASH_FILE}",
        )
        with open(VOICE_HASH_FILE, encoding="utf-8") as f:
            table = json.load(f)
        self.assertIsInstance(table, dict)
        self.assertGreater(len(table), 0, "voice hash 表为空")
        self.assertEqual(
            VOICE_HASH_TABLE,
            table,
            "single_parser 未使用 voice_hash_table.json 中的映射",
        )

    def test_parse_converts_all_sources_without_leftover_voice(self):
        """所有 source 均可转换，且不允许残留未转换的 {f81b} voice 控制字符。"""
        for fname, entry_id, source in self.sources:
            with self.subTest(file=fname, entry=entry_id):
                parsed = parse_single_entry(source)
                self.assertIsNone(
                    F81B_RE_CI.search(parsed),
                    "转换后仍残留未转换的 voice 控制字符 {f81b}",
                )

    def test_voice_placeholders_match_source_and_exist_in_hash_table(self):
        """每个 {f81b} 控制字符恰好转为一个占位符，且 hash 在 voice_hash_table.json 中。"""
        for fname, entry_id, source in self.sources:
            with self.subTest(file=fname, entry=entry_id):
                parsed = parse_single_entry(source)
                placeholders = VOICE_PLACEHOLDER_RE.findall(parsed)
                self.assertEqual(
                    len(placeholders),
                    len(F81B_RE_CI.findall(source)),
                    "voice 占位符数量与原文 {f81b} 控制字符数量不一致",
                )
                for role, voice_hash in placeholders:
                    self.assertTrue(role, "voice 占位符缺少角色名")
                    self.assertIn(
                        voice_hash,
                        VOICE_HASH_TABLE,
                        f"voice hash {voice_hash} 不在 voice_hash_table.json 中",
                    )

    def test_revert_restores_source_exactly(self):
        """revert 后必须与转换前文本完全一致。"""
        for fname, entry_id, source in self.sources:
            with self.subTest(file=fname, entry=entry_id):
                parsed = parse_single_entry(source)
                reverted = parse_single_entry_revert(parsed)
                self.assertEqual(reverted, source)


class EO5QuestPipelineTests(unittest.TestCase):
    """端到端：process_file / process_file_revert 可处理全部 QUEST 文件（临时目录）。"""

    def test_process_file_and_revert_run_on_all_quest_files(self):
        from loguru import logger

        from EO5.processor import process_file, process_file_revert

        logger.remove()  # 静默行长度 warning，保持测试输出干净
        try:
            files = sorted(p.name for p in QUEST_DIR.glob("*.xml"))
            self.assertTrue(files, "QUEST 目录下没有 XML 文件")
            for fname in files:
                with self.subTest(file=fname):
                    with tempfile.TemporaryDirectory() as tmp:
                        parsed_dir = Path(tmp) / "parsed"
                        reverted_dir = Path(tmp) / "reverted"
                        parsed_path = parsed_dir / fname
                        reverted_path = reverted_dir / fname
                        process_file(str(QUEST_DIR / fname), str(parsed_dir))
                        self.assertTrue(
                            parsed_path.is_file(), "process_file 未生成解析文件"
                        )
                        process_file_revert(str(parsed_path), str(reverted_dir))
                        self.assertTrue(
                            reverted_path.is_file(), "process_file_revert 未生成回填文件"
                        )
        finally:
            logger.add(sys.stderr)


if __name__ == "__main__":
    unittest.main()
