import logging
from ast import literal_eval
from functools import cached_property, lru_cache
from pathlib import Path
from xml.etree import ElementTree
import shutil


class ProcessJUnit:
    def __init__(self, new_report_xml_path: Path, tests_result_path: Path, tag: str):
        self.report_path = new_report_xml_path
        self.tests_result_path = tests_result_path
        self._summary = {"time": 0.0, "tests": 0, "errors": 0, "skipped": 0, "failures": 0}
        self.tag = tag

    @lru_cache(maxsize=None)
    def _create_report(self):
        if not self.tests_result_path.is_dir():
            raise NotADirectoryError(f"The {self.tests_result_path} directory not exits")

        new_tree = ElementTree.Element("testsuite")
        is_first_run = True
        for file_path in self.tests_result_path.glob("*.xml"):
            tree = ElementTree.parse(file_path)
            testsuite_element = next(tree.iter("testsuite"))
            for key in self._summary:
                self._summary[key] += literal_eval(testsuite_element.attrib[key])

            if is_first_run:
                is_first_run = False
                properties_element = tree.find("properties")
                new_properties_element = ElementTree.SubElement(
                    new_tree, properties_element.tag, attrib=properties_element.attrib)
                _ = [ElementTree.SubElement(new_properties_element, element.tag, attrib=element.attrib)
                     for element in properties_element]
            for testcase_parent_element in tree.iterfind("testcase"):
                attrib = testcase_parent_element.attrib
                attrib['classname'] = f"{self.tag}.{attrib['classname']}"
                new_testcase_parent_element = ElementTree.SubElement(
                    new_tree, testcase_parent_element.tag, attrib=testcase_parent_element.attrib)
                _ = [ElementTree.SubElement(new_testcase_parent_element, testcase_child_element.tag,
                                            attrib=testcase_child_element.attrib)
                     for testcase_child_element in testcase_parent_element]

        new_tree.attrib["name"] = self.report_path.stem
        new_tree.attrib.update({key: str(value) for key, value in self._summary.items()})
        new_tree.attrib["time"] = f"{self._summary['time']:.3f}"
        logging.info("Creating a new report file in '%s' path", self.report_path)
        self.report_path.parent.mkdir(exist_ok=True)
        with self.report_path.open(mode="w", encoding="utf-8") as file:
            file.write(ElementTree.tostring(element=new_tree, encoding="utf-8").decode())

    @cached_property
    def summary(self):
        self._create_report()
        return self._summary

    @cached_property
    def is_failed(self) -> bool:
        return not (self.summary["tests"] and self.summary["errors"] == self.summary["failures"] == 0)

    def clear_original_reports(self):
        logging.info("Removing all run's xml files of '%s' version", self.tag)
        shutil.rmtree(self.tests_result_path)

