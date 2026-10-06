"""Build-time fixtures use the same Lua decoder as the actual pinned imports."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Tools"))
import import_variants as variants


class VariantFixtures(unittest.TestCase):
    def test_global_and_addon_sources(self):
        lua = ["wsl", "-d", "Debian", "-e", "lua5.1"] if sys.platform == "win32" else ["lua5.1"]
        global_source = b'MultiLanguageItemData["de"][25] = {name="Schwert", additional_info="Text\\nZeile"}'
        addon_source = b'local name,addon = ...; addon.itemData.de = {[25]={name="Schwert", additional_info="Text\\nZeile"}}'
        expected = {"25": {"name": "Schwert", "additional_info": "Text\nZeile"}}
        self.assertEqual(variants.read_payload(global_source, "item", "deDE", lua), expected)
        self.assertEqual(variants.read_payload(addon_source, "item", "deDE", lua), expected)

    def test_quality_preserves_ordinary_names(self):
        self.assertTrue(variants.developer_reason("Waypoint (Only GM can see it)", "npc"))
        self.assertTrue(variants.developer_reason("zzOLD Fireball", "spell"))
        self.assertTrue(variants.developer_reason("Monster - Sword", "item"))
        self.assertFalse(variants.developer_reason("Test of Faith", "item"))
        self.assertFalse(variants.developer_reason("Training Dummy", "npc"))

    def test_compressed_sources_are_deterministic(self):
        self.assertEqual(variants.base.deterministic_gzip(b"source"), variants.base.deterministic_gzip(b"source"))

    def test_guards_fail_closed(self):
        lua = ["wsl", "-d", "Debian", "-e", "lua5.1"] if sys.platform == "win32" else ["lua5.1"]
        cases = [
            ("classic", "2.5.6", "tbc"), ("classic", "3.4.3", "wrath"),
            ("classic", "4.4.2", "cata"), ("classic", "5.5.2", "mop-classic"),
            ("retail", "12.0.1", "retail"), ("retail", "2.5.6", "retail"),
            ("forever", "1.60.0", "forever"), ("classic", "1.15.9", None),
            ("sod", "1.15.9", None), ("unknown", "2.5.6", None),
            ("", "3.4.3", None), (2, "4.4.2", None),
            ("classic", 2, None), ("classic", "2.bad", None),
            ("classic", "3.4.bad", None), ("classic", "not-a-version", None),
        ]
        checks = []
        for flavor, version, expected in cases:
            checks.append("WordHunterWoW_Addon={Compat={GameFlavor=function() return " + variants.base.literal(flavor) + " end}}\nGetBuildInfo=function() return " + variants.base.literal(version) + " end\n")
            for edition in variants.EDITIONS:
                checks.append("do local activate=function()\n" + variants.guard(edition) + "return true end\nassert(activate() == " + ("true" if edition == expected else "nil") + ", " + variants.base.quote(str(flavor) + "/" + str(version) + "/" + edition) + ") end\n")
        result = variants.subprocess.run(lua + ["-"], input="".join(checks), encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
