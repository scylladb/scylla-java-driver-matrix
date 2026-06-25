from pathlib import Path
from xml.etree import ElementTree
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from processjunit import ProcessJUnit


def test_create_report_preserves_testcase_diagnostics(tmp_path):
    source_reports = tmp_path / "failsafe-reports"
    source_reports.mkdir()
    output_report = tmp_path / "reports" / "TEST-datastax-4.19.3.xml"

    (source_reports / "TEST-com.example.DriverIT.xml").write_text(
        """\
<testsuite name="DriverIT" tests="2" errors="1" skipped="0" failures="1" time="1.500">
  <properties>
    <property name="it.test" value="DriverIT"/>
  </properties>
  <testcase classname="com.example.DriverIT" name="fails" time="0.100">
    <failure message="boom" type="AssertionError">stack line 1
stack line 2</failure>
    <system-out>stdout details</system-out>
  </testcase>
  <testcase classname="com.example.DriverIT" name="errors" time="0.200">
    <error message="bad" type="RuntimeError">error line 1
error line 2</error>
    <system-err>stderr details</system-err>
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    report = ProcessJUnit(
        new_report_xml_path=output_report,
        tests_result_path=source_reports,
        tag="4.19.3",
        driver_type="datastax",
    )

    assert report.summary == {"time": 1.5, "tests": 2, "errors": 1, "skipped": 0, "failures": 1}

    root = ElementTree.parse(output_report).getroot()
    assert root.find("./properties/property").attrib == {"name": "it.test", "value": "DriverIT"}
    testcases = root.findall("./testcase")
    assert testcases[0].attrib["classname"] == "datastax.4.19.3.com.example.DriverIT"
    assert testcases[0].find("failure").text == "stack line 1\nstack line 2"
    assert testcases[0].find("system-out").text == "stdout details"
    assert testcases[1].find("error").text == "error line 1\nerror line 2"
    assert testcases[1].find("system-err").text == "stderr details"
