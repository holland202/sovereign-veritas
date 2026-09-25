"""Thermal evidence: per-zone, typed, per-domain - never a cross-domain mean.

Fixture = the 68 zone types read on the S25 (SM-S938U) on 2026-09-25, with the idle values from
that dump. Zones 15/45/57 were not captured at idle; 37000 stands in for them.
"""
import os

from sovereign_veritas.thermal import classify, read_zones, summarize

OBSERVED = {
    0: ("aoss-0", 37400), 1: ("cpu-0-0-0", 40500), 2: ("cpu-0-0-1", 40100), 3: ("cpu-0-1-0", 39000),
    4: ("cpu-0-1-1", 40100), 5: ("cpu-0-2-0", 39000), 6: ("cpu-0-2-1", 39300), 7: ("cpu-0-3-0", 39000),
    8: ("cpu-0-3-1", 39300), 9: ("cpu-0-4-0", 40500), 10: ("cpu-0-4-1", 38600), 11: ("cpu-0-5-0", 38600),
    12: ("cpu-0-5-1", 38200), 13: ("cpuss-0-0", 40100), 14: ("cpuss-0-1", 40100), 15: ("aoss-1", 37000),
    16: ("cpu-1-0-0", 37600), 17: ("cpu-1-0-1", 38000), 18: ("cpu-1-1-0", 37600), 19: ("cpu-1-1-1", 38000),
    20: ("cpuss-1-0", 38400), 21: ("cpuss-1-1", 38400), 22: ("aoss-2", 37600), 23: ("gpuss-0", 37300),
    24: ("gpuss-1", 37600), 25: ("gpuss-2", 37600), 26: ("gpuss-3", 37600), 27: ("gpuss-4", 38000),
    28: ("gpuss-5", 38000), 29: ("gpuss-6", 38000), 30: ("gpuss-7", 37300), 31: ("mdmss-0", 37600),
    32: ("mdmss-1", 37300), 33: ("mdmss-2", 37300), 34: ("mdmss-3", 37300), 35: ("camera-0", 37300),
    36: ("camera-1", 37600), 37: ("video", 37300), 38: ("aoss-3", 37300), 39: ("nsphvx-0", 37300),
    40: ("nsphvx-1", 37600), 41: ("nsphvx-2", 37300), 42: ("nsphmx-0", 37300), 43: ("nsphmx-1", 37300),
    44: ("nsphmx-2", 37600), 45: ("nsphmx-3", 37000), 46: ("ddr", 37600), 47: ("pm8550-bcl-lvl0", 0),
    48: ("pm8550-bcl-lvl1", 0), 49: ("pm8550-bcl-lvl2", 0), 50: ("pm8550ve_f_tz", 37000),
    51: ("pmr735d_tz", 37000), 52: ("sys-therm-5", 25491), 53: ("sys-therm-0", 33617),
    54: ("pm8550ve_g_tz", 34830), 55: ("pm8550ve_i_tz", 34361), 56: ("pm8550vs_j_tz", 34428),
    57: ("pm8550_tz", 37000), 58: ("pm8550ve_d_tz", 35900), 59: ("ac", 34200), 60: ("battery", 32100),
    61: ("sdr0_pa", -273000), 62: ("sdr0", 33000), 63: ("mmw_ific0", 33000), 64: ("mmw0", -273000),
    65: ("mmw1", -273000), 66: ("mmw2", -273000), 67: ("mmw3", -273000),
}


def tree(tmp_path, overrides=None):
    for i, (ztype, value) in OBSERVED.items():
        d = tmp_path / f"thermal_zone{i}"
        d.mkdir()
        (d / "type").write_text(ztype + "\n")
        value = (overrides or {}).get(i, value)
        if value is not None:
            (d / "temp").write_text(f"{value}\n")
    return str(tmp_path)


def test_every_observed_type_has_a_domain_except_ac():
    unknown = {t for t, _ in OBSERVED.values() if classify(t) == "unknown"}
    assert unknown == {"ac"}
    assert classify("cpuss-0-0") == "cpu_subsystem" and classify("cpu-1-1-1") == "cpu_core"
    assert classify("pm8550-bcl-lvl0") == "bcl" and classify("pm8550_tz") == "pmic"


def test_observed_device_statuses(tmp_path):
    readings = read_zones(tree(tmp_path))
    assert len(readings) == 68
    assert summarize(readings)["status_counts"] == {"not_temperature": 3, "offline": 5, "ok": 60}


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)


def test_hot_core_stays_in_its_domain_and_nothing_is_averaged(tmp_path):
    s = summarize(read_zones(tree(tmp_path, {19: 104200})))  # probe max on cpu-1-1-1
    assert s["domains"]["cpu_core"]["max_c"] == 104.2
    assert s["domains"]["battery"]["max_c"] == 32.1
    assert s["domains"]["bcl"]["max_c"] is None
    assert not {k for k in _keys(s) if "mean" in k or k == "max_c_all"}


def test_unreadable_and_implausible_zones_are_excluded(tmp_path):
    readings = {r.zone: r for r in read_zones(tree(tmp_path, {1: None, 2: 999999}))}
    assert readings["thermal_zone1"].status == "unreadable"
    assert readings["thermal_zone2"].status == "out_of_range"
    assert readings["thermal_zone2"].celsius is None


def test_missing_root_is_empty_not_an_exception(tmp_path):
    assert read_zones(os.path.join(str(tmp_path), "absent")) == ()
