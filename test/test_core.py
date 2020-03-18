import copy
from unittest import TestCase

import lxml
import lxml.html

from src import core


# noinspection PyArgumentList
from src import utils

RESOURCES_DIRECTORY = "./rsrc"


class TestGNode(TestCase):
    def test_equality(self):
        self.assertEqual(
            core.GNode("table-3", 3, 5), core.GNode("table-3", 3, 5)
        )
        self.assertIsNot(
            core.GNode("table-3", 3, 5), core.GNode("table-3", 3, 5)
        )

    def test__extra_format(self):
        gn = core.GNode("table-3", 3, 5)
        self.assertIsInstance(gn._extra_format("!S"), str)
        self.assertRaises(NotImplementedError, gn._extra_format, "!s")
        self.assertRaises(NotImplementedError, gn._extra_format, "d")

    def test_size(self):
        gn = core.GNode("table-3", 3, 5)
        self.assertEqual(gn.size, 2)

    def test_dunders(self):
        gn = core.GNode("table-3", 3, 5)
        "{}".format(gn)
        "{:!s}".format(gn)
        "{:!S}".format(gn)
        "{:!r}".format(gn)
        self.assertEqual(len(gn), 2)


# noinspection PyArgumentList
class TestGNodePair(TestCase):
    def test_equality(self):
        self.assertEqual(
            core.GNodePair(
                core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)
            ),
            core.GNodePair(
                core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)
            ),
        )
        self.assertIsNot(
            core.GNodePair(
                core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)
            ),
            core.GNodePair(
                core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)
            ),
        )

    def test__extra_format(self):
        gnpair = core.GNodePair(
            core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)
        )
        self.assertRaises(NotImplementedError, gnpair._extra_format, "!S")
        self.assertRaises(NotImplementedError, gnpair._extra_format, "!s")
        self.assertRaises(NotImplementedError, gnpair._extra_format, "d")

    def test_dunders(self):
        gnpair = core.GNodePair(
            core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)
        )
        "{}".format(gnpair)
        "{:!s}".format(gnpair)
        "{:!S}".format(gnpair)
        "{:!r}".format(gnpair)


# noinspection PyArgumentList
class TestDataRegion(TestCase):
    def test_equality(self):
        core.DataRegion("body", 3, 5, 9)
        self.assertEqual(
            core.DataRegion("body", 3, 5, 9), core.DataRegion("body", 3, 5, 9)
        )
        self.assertIsNot(
            core.DataRegion("body", 3, 5, 9), core.DataRegion("body", 3, 5, 9)
        )

    def test__extra_format(self):
        dr = core.DataRegion(
            parent="body",
            gnode_size=3,
            first_gnode_start_index=5,
            n_nodes_covered=9,
        )
        self.assertIsInstance(dr._extra_format("!S"), str)
        self.assertRaises(NotImplementedError, dr._extra_format, "!s")
        self.assertRaises(NotImplementedError, dr._extra_format, "d")

    def test_empty(self):
        dr = core.DataRegion.empty()
        self.assertIsNone(dr[0])
        self.assertEqual(dr.n_nodes_covered, 0)

    def test_binary_from_last_gnode(self):
        gn = core.GNode("table-0", 4, 6)
        dr = core.DataRegion.binary_from_last_gnode(gn)
        self.assertEqual(dr.parent, gn.parent)
        self.assertEqual(dr.gnode_size, gn.size)
        self.assertEqual(dr.first_gnode_start_index, gn.start - gn.size)
        self.assertEqual(dr.n_nodes_covered, 2 * gn.size)
        self.assertEqual(dr.last_covered_tag_index, gn.end - 1)
        self.assertEqual(dr.n_gnodes, 2)
        self.assertTrue(4 in dr)
        self.assertTrue(5 in dr)
        self.assertFalse(6 in dr)

    def test_is_empty(self):
        empty = core.DataRegion.empty()
        non_empty = core.DataRegion("table-0", 1, 5, 3)
        self.assertTrue(empty.is_empty)
        self.assertFalse(non_empty.is_empty)

    def test_n_gnodes(self):
        dr = core.DataRegion("tr-9", 2, 0, 2 * 3)
        self.assertEqual(dr.n_gnodes, 3)

    def test_last_covered_tag_index(self):
        dr = core.DataRegion("tr-9", 2, 0, 2 * 3)
        self.assertEqual(dr.last_covered_tag_index, 5)

    def test_extend_one_gnode(self):
        dr = core.DataRegion("tr-9", 2, 0, 2 * 3)
        dr_ext = dr.extend_one_gnode()
        self.assertEqual(dr_ext, core.DataRegion("tr-9", 2, 0, 2 * 4))

    def test_dunders(self):
        dr = core.DataRegion("tr-9", 2, 5, 2 * 2)
        "{}".format(dr)
        "{:!s}".format(dr)
        "{:!S}".format(dr)
        "{:!r}".format(dr)
        self.assertTrue(4 not in dr)
        self.assertTrue(9 not in dr)
        self.assertTrue(all(i in dr for i in range(5, 9)))
        gnodes = list(dr)
        self.assertEqual(len(gnodes), 2)
        self.assertEqual(gnodes[0], core.GNode("tr-9", 5, 7))
        self.assertEqual(gnodes[1], core.GNode("tr-9", 7, 9))


class TestDataRecord(TestCase):
    pass


class TestMDR(TestCase):

    SIMPLEST_HTML_EVER = """
    <!DOCTYPE html>
    <html>
        <body>
        <table>
            <tr><th>X</th><th>Y</th></tr>    <tr><td>2</td><td>4</td></tr>
        </table>
        </body>
    </html>
    """

    def _get_simplest_html_ever(self) -> lxml.html.HtmlElement:
        return lxml.html.fromstring(self.SIMPLEST_HTML_EVER)

    def _get_table_0(self):
        return copy.deepcopy(self._table_0)

    @classmethod
    def setUpClass(cls):
        cls._table_0 = utils.open_html_document(
            RESOURCES_DIRECTORY, "table-0.html"
        )

    def test_used_mdr(self):
        table_0 = self._get_table_0()
        mdr = core.MDR()
        mdr(table_0)
        self.assertRaises(core.UsedMDRException, mdr, table_0)

    def test__debug(self):
        mdr = core.MDR()
        mdr._debug("hello0", tabs=0, force=True)
        mdr._debug("hello1", tabs=1, force=True)
        mdr._debug_phase(0)
        mdr._debug_phase(2)
        mdr._debug_phase(4)

    def test_depth(self):
        html = self._get_simplest_html_ever()
        self.assertEqual(core.MDR.depth(html), 0)
        self.assertEqual(core.MDR.depth(html[0]), 1)
        self.assertEqual(core.MDR.depth(html[0][0]), 2)
        self.assertEqual(core.MDR.depth(html[0][0][0]), 3)
        self.assertEqual(core.MDR.depth(html[0][0][1]), 3)

    def test_nodes_to_string(self):
        html = self._get_simplest_html_ever()
        tr0 = html[0][0][0]
        x: lxml.html.HtmlElement = tr0[0]
        y: lxml.html.HtmlElement = tr0[1]
        self.assertEqual(core.MDR.nodes_to_string([x]), "<th>X</th>")
        self.assertEqual(core.MDR.nodes_to_string([y]), "<th>Y</th>")
        self.assertEqual(
            core.MDR.nodes_to_string([x, y]), "<th>X</th> <th>Y</th>"
        )

        tr1 = html[0][0][1]
        self.assertEqual(
            core.MDR.nodes_to_string([tr0]), "<tr><th>X</th><th>Y</th></tr>"
        )
        self.assertEqual(
            core.MDR.nodes_to_string([tr0, tr1]),
            "<tr><th>X</th><th>Y</th></tr> <tr><td>2</td><td>4</td></tr>",
        )

    def test__compute_distances(self):
        table_0 = self._get_table_0()
        mdr = core.MDR()
        mdr(table_0)

        self.assertEqual(len(mdr.distances), 27)

        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("html")}), 1
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("style")}), 1
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("head")}), 1
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("body")}), 1
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("h2")}), 1
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("div")}), 1
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("table")}), 1
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("tr")}), 4
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("th")}), 4
        )
        self.assertEqual(
            len({k for k in mdr.distances if k.startswith("td")}), 12
        )

        self.assertIsNone(mdr.distances["html-00000"])
        self.assertIsNone(mdr.distances["body-00000"])
        self.assertIsNone(mdr.distances["div-00000"])

        self.assertIn(1, mdr.distances["table-00000"])
        self.assertIn(2, mdr.distances["table-00000"])
        self.assertNotIn(3, mdr.distances["table-00000"])

        self.assertNotIn(1, mdr.distances["td-00000"])

        self.assertEqual(len(mdr.distances["table-00000"][1]), 3)
        self.assertEqual(len(mdr.distances["table-00000"][2]), 1)

        index_pairs = {
            tuple(tuple(v for v in x if isinstance(v, int)) for x in p)
            for p in mdr.distances["tr-00000"][1]
        }
        self.assertIn(((0, 1), (1, 2)), index_pairs)
        self.assertIn(((1, 2), (2, 3)), index_pairs)
        self.assertIn(((2, 3), (3, 4)), index_pairs)
        self.assertNotIn(((3, 4), (4, 5)), index_pairs)

    def test__compare_combinations(self):
        def get_html_table(n_rows):
            html_str = "<table>"
            for i in range(n_rows):
                html_str += "<tr><td>{}</td></tr>".format(str(i))
            html_str += "</table>"
            return lxml.html.fromstring(html_str)

        mdr = core.MDR()
        table_3 = get_html_table(3)
        distances = mdr._compare_combinations(table_3.getchildren())
        self.assertIn(1, distances)
        self.assertEqual(len(distances[1]), 2)
        self.assertNotIn(2, distances)

        mdr = core.MDR()
        table_10 = get_html_table(10)
        distances = mdr._compare_combinations(table_10.getchildren())
        self.assertTrue(all(i in distances for i in range(1, 5 + 1)))
        self.assertNotIn(6, distances)
        self.assertEqual(len(distances[1]), 9)
        self.assertEqual(len(distances[2]), 4 + 3)
        self.assertEqual(len(distances[3]), 2 + 2 + 1)
        self.assertEqual(len(distances[4]), 1 + 1 + 1 + 0)
        self.assertEqual(len(distances[5]), 1 + 0 + 0 + 0 + 0)

        mdr = core.MDR()
        table_100 = get_html_table(100)
        distances = mdr._compare_combinations(table_100.getchildren())
        self.assertTrue(all(i in distances for i in range(1, 10 + 1)))
        self.assertNotIn(11, distances)

    def test__identify_data_regions(self):
        self.fail()

    def test__find_data_regions(self):

        self.fail()

    def test__uncovered_data_regions(self):
        self.fail()

    def test__find_data_records(self):
        self.fail()

    def test__find_records_1(self):
        self.fail()

    def test__find_records_n(self):
        self.fail()

    def test_get_data_records_as_node_lists(self):
        self.fail()
