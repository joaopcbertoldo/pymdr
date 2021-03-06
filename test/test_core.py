import copy
import pathlib
from typing import Dict, Tuple, Set
from unittest import TestCase

import lxml
import lxml.html

import files_management
import core


RESOURCES_DIRECTORY = "./rsrc"


# noinspection PyArgumentList
class TestGNode(TestCase):
    def test_equality(self):
        self.assertEqual(core.GNode("table-3", 3, 5), core.GNode("table-3", 3, 5))
        self.assertIsNot(core.GNode("table-3", 3, 5), core.GNode("table-3", 3, 5))

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
            core.GNodePair(core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)),
            core.GNodePair(core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)),
        )
        self.assertIsNot(
            core.GNodePair(core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)),
            core.GNodePair(core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7)),
        )

    def test__extra_format(self):
        gnpair = core.GNodePair(core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7))
        self.assertRaises(NotImplementedError, gnpair._extra_format, "!S")
        self.assertRaises(NotImplementedError, gnpair._extra_format, "!s")
        self.assertRaises(NotImplementedError, gnpair._extra_format, "d")

    def test_dunders(self):
        gnpair = core.GNodePair(core.GNode("table-3", 3, 5), core.GNode("table-3", 5, 7))
        "{}".format(gnpair)
        "{:!s}".format(gnpair)
        "{:!r}".format(gnpair)


# noinspection PyArgumentList
class TestDataRegion(TestCase):
    def test_equality(self):
        core.DataRegion("body", 3, 5, 9)
        self.assertEqual(core.DataRegion("body", 3, 5, 9), core.DataRegion("body", 3, 5, 9))
        self.assertIsNot(core.DataRegion("body", 3, 5, 9), core.DataRegion("body", 3, 5, 9))

    def test__extra_format(self):
        dr = core.DataRegion(
            parent="body", gnode_size=3, first_gnode_start_index=5, n_nodes_covered=9,
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
        gnodes = list(dr.get_gnode_iterator())
        self.assertEqual(len(gnodes), 2)
        self.assertEqual(gnodes[0], core.GNode("tr-9", 5, 7))
        self.assertEqual(gnodes[1], core.GNode("tr-9", 7, 9))


class TestDataRecord(TestCase):
    pass


# noinspection PyArgumentList,DuplicatedCode
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
        table_0_filepath = pathlib.Path(RESOURCES_DIRECTORY).joinpath("table-0.html").absolute()
        cls._table_0 = files_management.open_html_document(table_0_filepath, remove_stuff=False)

    def test_used_mdr(self):
        table_0 = self._get_table_0()
        mdr = core.MDR.with_defaults(table_0)
        mdr()
        self.assertRaises(core.UsedMDRException, mdr)

    def test_depth(self):
        html = self._get_simplest_html_ever()
        self.assertEqual(core.depth(html), 0)
        self.assertEqual(core.depth(html[0]), 1)
        self.assertEqual(core.depth(html[0][0]), 2)
        self.assertEqual(core.depth(html[0][0][0]), 3)
        self.assertEqual(core.depth(html[0][0][1]), 3)

    def test_nodes_to_string(self):
        html = self._get_simplest_html_ever()
        tr0 = html[0][0][0]
        x: lxml.html.HtmlElement = tr0[0]
        y: lxml.html.HtmlElement = tr0[1]
        self.assertEqual(core.nodes_to_string([x], False), "<th>X</th>")
        self.assertEqual(core.nodes_to_string([y], False), "<th>Y</th>")
        self.assertEqual(core.nodes_to_string([x, y], False), "<th>X</th> <th>Y</th>")

        tr1 = html[0][0][1]
        self.assertEqual(core.nodes_to_string([tr0], False), "<tr><th>X</th><th>Y</th></tr>")
        self.assertEqual(
            core.nodes_to_string([tr0, tr1], False),
            "<tr><th>X</th><th>Y</th></tr> <tr><td>2</td><td>4</td></tr>",
        )

    def test__compute_distances(self):
        table_0 = self._get_table_0()
        distances = {}
        node_namer = core.NodeNamer()
        node_namer.load(table_0)
        core.compute_distances(table_0, distances, {}, node_namer, 3, 10)

        self.assertEqual(len(distances), 27)

        self.assertEqual(len({k for k in distances if k.startswith("html")}), 1)
        self.assertEqual(len({k for k in distances if k.startswith("style")}), 1)
        self.assertEqual(len({k for k in distances if k.startswith("head")}), 1)
        self.assertEqual(len({k for k in distances if k.startswith("body")}), 1)
        self.assertEqual(len({k for k in distances if k.startswith("h2")}), 1)
        self.assertEqual(len({k for k in distances if k.startswith("div")}), 1)
        self.assertEqual(len({k for k in distances if k.startswith("table")}), 1)
        self.assertEqual(len({k for k in distances if k.startswith("tr")}), 4)
        self.assertEqual(len({k for k in distances if k.startswith("th")}), 4)
        self.assertEqual(len({k for k in distances if k.startswith("td")}), 12)

        self.assertIsNone(distances["html-00000"])
        self.assertIsNone(distances["body-00000"])
        self.assertIsNone(distances["div-00000"])

        self.assertIn(1, distances["table-00000"])
        self.assertIn(2, distances["table-00000"])
        self.assertNotIn(3, distances["table-00000"])

        self.assertNotIn(1, distances["td-00000"])

        self.assertEqual(len(distances["table-00000"][1]), 3)
        self.assertEqual(len(distances["table-00000"][2]), 1)

        index_pairs = {
            tuple(tuple(v for v in x if isinstance(v, int)) for x in p)
            for p in distances["tr-00000"][1]
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

        table_3 = get_html_table(3)
        distances = core._compare_combinations(table_3.getchildren(), "table-00000", 10)
        self.assertIn(1, distances)
        self.assertEqual(len(distances[1]), 2)
        self.assertNotIn(2, distances)

        table_10 = get_html_table(10)
        distances = core._compare_combinations(table_10.getchildren(), "table-00000", 10)
        self.assertTrue(all(i in distances for i in range(1, 5 + 1)))
        self.assertNotIn(6, distances)
        self.assertEqual(len(distances[1]), 9)
        self.assertEqual(len(distances[2]), 4 + 3)
        self.assertEqual(len(distances[3]), 2 + 2 + 1)
        self.assertEqual(len(distances[4]), 1 + 1 + 1 + 0)
        self.assertEqual(len(distances[5]), 1 + 0 + 0 + 0 + 0)

        table_100 = get_html_table(100)
        distances = core._compare_combinations(table_100.getchildren(), "table-00000", 10)
        self.assertTrue(all(i in distances for i in range(1, 10 + 1)))
        self.assertNotIn(11, distances)

    def test__identify_data_regions(self):
        node_name = "doenst-matter"
        too_far = 0.9
        close_enough = 0.1
        mock_threshold = 0.5

        def idx_pair_to_gnode_pair(
            idx_pair: Tuple[Tuple[int, int], Tuple[int, int]]
        ) -> Dict[core.GNodePair, float]:
            return core.GNodePair(
                core.GNode(node_name, idx_pair[0][0], idx_pair[0][1]),
                core.GNode(node_name, idx_pair[1][0], idx_pair[1][1]),
            )

        def index_pairs_to_classes(
            distances_: Dict[int, Dict[Tuple[Tuple[int, int], Tuple[int, int]], float]]
        ) -> Dict[int, Dict[core.GNodePair, float]]:
            return {
                gnode_size: {
                    idx_pair_to_gnode_pair(idx_pair): dist for idx_pair, dist in dic.items()
                }
                for gnode_size, dic in distances_.items()
            }

        def test_input_output_pair(
            n_children: int,
            distances_dict: Dict[int, Dict[Tuple[Tuple[int, int], Tuple[int, int]], float]],
            expected_data_regions: Set[core.DataRegion],
        ):
            actual_data_regions = core._identify_data_regions(
                start_index=0,
                node_name=node_name,
                n_children=n_children,
                node_distances=index_pairs_to_classes(distances_dict),
                distance_threshold=mock_threshold,
                max_tag_per_gnode=10,
            )
            self.assertEqual(expected_data_regions, actual_data_regions)

        input_output_pairs = [
            # 0
            (
                3,  # n_children
                {1: {((0, 1), (1, 2)): close_enough, ((1, 2), (2, 3)): close_enough}},
                {core.DataRegion(node_name, 1, 0, 3)},
            ),
            # 1
            (
                3,  # n_children
                {1: {((0, 1), (1, 2)): close_enough, ((1, 2), (2, 3)): too_far}},
                {core.DataRegion(node_name, 1, 0, 2)},
            ),
            # 2
            (
                5,  # n_children
                {
                    1: {
                        ((0, 1), (1, 2)): close_enough,
                        ((1, 2), (2, 3)): close_enough,
                        ((2, 3), (3, 4)): too_far,
                        ((3, 4), (4, 5)): close_enough,
                    },
                    2: {((0, 2), (2, 4)): too_far, ((1, 3), (3, 5)): close_enough},
                },
                {
                    core.DataRegion(
                        node_name, gnode_size=1, first_gnode_start_index=0, n_nodes_covered=3,
                    ),
                    core.DataRegion(
                        node_name, gnode_size=1, first_gnode_start_index=3, n_nodes_covered=2,
                    ),
                },
            ),
            # 3
            (
                5,  # n_children
                {
                    1: {
                        ((0, 1), (1, 2)): close_enough,
                        ((1, 2), (2, 3)): close_enough,
                        ((2, 3), (3, 4)): too_far,
                        ((3, 4), (4, 5)): close_enough,
                    },
                    2: {((0, 2), (2, 4)): close_enough, ((1, 3), (3, 5)): too_far},
                },
                {
                    core.DataRegion(
                        node_name, gnode_size=2, first_gnode_start_index=0, n_nodes_covered=4,
                    )
                },
            ),
        ]

        for i, (n_children, distances, data_regions) in enumerate(input_output_pairs):
            # print("case {}".format(i))  # uncomment for debugging
            test_input_output_pair(n_children, distances, data_regions)

        # todo(unittest): fill in more meaningful cases

    def test__uncovered_data_regions(self):
        parent_node_name = "doesnt-matter"
        dr_from_0_to_2 = core.DataRegion(
            parent_node_name, gnode_size=1, first_gnode_start_index=0, n_nodes_covered=3,
        )
        dr_from_5_to_10 = core.DataRegion(
            parent_node_name, gnode_size=2, first_gnode_start_index=5, n_nodes_covered=6,
        )

        in_out_tuples = [
            ({dr_from_0_to_2}, 1, False,),
            ({dr_from_0_to_2}, 2, False,),
            ({dr_from_0_to_2}, 3, True,),
            ({dr_from_0_to_2}, 7, True,),
            ({dr_from_0_to_2, dr_from_5_to_10}, 7, False,),
            ({dr_from_0_to_2, dr_from_5_to_10}, 15, True,),
        ]

        def test_input_output_tuples(
            drs_: Set[core.DataRegion], child_idx_: int, expected_answer_: bool
        ):
            answer_ = core._uncovered_data_regions(drs_, child_idx_)
            self.assertEqual(answer_, expected_answer_)

        for tuple_ in in_out_tuples:
            test_input_output_tuples(*tuple_)

    def _compare_all_data_records(self, expected_data_records_, actual_data_records_):
        self.assertEqual(len(expected_data_records_), len(actual_data_records_))
        for i, (expected_, actual_) in enumerate(
            zip(sorted(expected_data_records_), sorted(actual_data_records_))
        ):
            self.assertEqual(expected_, actual_, "data record idx `{}`".format(str(i)))

    def test__find_records_1(self):
        mocked_edit_dist_threshold = 0.5
        too_far = 0.9
        close_enough = 0.1
        max_tag_per_gnode = 10  # doesn't really matter

        # case 0
        html_str = "<body><div></div> ... </body>"
        body = lxml.html.fromstring(html_str)
        node_namer = core.NodeNamer()
        node_namer.load(body)
        div_0 = body[0]

        # case 1
        html_str = (
            "<body><div><span></span><span></span><span></span><span></span></div> ... </body>"
        )
        body = lxml.html.fromstring(html_str)
        node_namer = core.NodeNamer()
        node_namer.load(body)
        div_0 = body[0]
        gnode = core.GNode(node_namer(body), 0, 1)

        distances = {
            node_namer(div_0): {
                1: {
                    ((0, 1), (1, 2)): close_enough,
                    ((1, 2), (2, 3)): close_enough,
                    ((2, 3), (3, 4)): close_enough,
                }
            },
        }
        div_0.tag = "tr"  # forcing a condition
        expected = [core.DataRecord([copy.deepcopy(gnode)])]
        actual = core._find_records_1(
            gnode, div_0, distances, node_namer, mocked_edit_dist_threshold, max_tag_per_gnode
        )
        self._compare_all_data_records(expected, actual)
        div_0.tag = "span"

        # case 2
        distances = {
            node_namer(div_0): {
                1: {
                    ((0, 1), (1, 2)): close_enough,
                    ((1, 2), (2, 3)): close_enough,
                    ((2, 3), (3, 4)): too_far,
                }
            },
        }
        expected = [core.DataRecord([copy.deepcopy(gnode)])]
        actual = core._find_records_1(
            gnode, div_0, distances, node_namer, mocked_edit_dist_threshold, max_tag_per_gnode
        )
        self._compare_all_data_records(expected, actual)

        # case 3
        distances = {
            node_namer(div_0): {
                1: {
                    ((0, 1), (1, 2)): too_far,
                    ((1, 2), (2, 3)): close_enough,
                    ((2, 3), (3, 4)): close_enough,
                }
            },
        }
        expected = [core.DataRecord([copy.deepcopy(gnode)])]
        actual = core._find_records_1(
            gnode, div_0, distances, node_namer, mocked_edit_dist_threshold, max_tag_per_gnode
        )
        self._compare_all_data_records(expected, actual)

        # case 4
        distances = {
            node_namer(div_0): {
                1: {
                    ((0, 1), (1, 2)): close_enough,
                    ((1, 2), (2, 3)): close_enough,
                    ((2, 3), (3, 4)): close_enough,
                }
            },
        }
        expected = [
            core.DataRecord([core.GNode(node_namer(div_0), 0, 1)]),
            core.DataRecord([core.GNode(node_namer(div_0), 1, 2)]),
            core.DataRecord([core.GNode(node_namer(div_0), 2, 3)]),
            core.DataRecord([core.GNode(node_namer(div_0), 3, 4)]),
        ]
        actual = core._find_records_1(
            gnode, div_0, distances, node_namer, mocked_edit_dist_threshold, max_tag_per_gnode
        )
        self._compare_all_data_records(expected, actual)

    def test__find_records_1_paper_examples(self):
        """Examples from the technical report version (see reference in core.py)."""

        mocked_edit_dist_threshold = 0.5
        close_enough = 0.1
        max_tag_per_gnode = 10  # this one doesn't really matter

        # Figure 11
        # | Obj1 | Obj2 |
        # | Obj3 | Obj4 |
        html_str = """
            <div>
                <div>
                    <div>
                        <div>
                            <div><span>Joao</span><span>25</span><span>M</span></div>
                        </div>
                        <div>
                            <div><span>Maria</span><span>30</span><span>F</span></div>
                        </div>
                    </div>
                    <div>
                        <div>
                            <div><span>Tiao</span><span>50</span><span>M</span></div>
                        </div>
                        <div>
                            <div><span>Bruna</span><span>25</span><span>F</span></div>
                        </div>
                    </div>
                </div>
            </div>
        """
        div_root = lxml.html.fromstring(html_str)
        node_namer = core.NodeNamer()
        node_namer.load(div_root)
        table = div_root[0]
        tr0, tr1 = table[0], table[1]
        tr0_gnode = core.GNode(node_namer(table), 0, 1)
        tr1_gnode = core.GNode(node_namer(table), 1, 2)
        tr0_name = node_namer(tr0)
        tr1_name = node_namer(tr1)
        distances = {
            tr0_name: {1: {((0, 1), (1, 2)): close_enough}},
            tr1_name: {1: {((0, 1), (1, 2)): close_enough}},
        }

        expected = [
            core.DataRecord([core.GNode(tr0_name, 0, 1)]),
            core.DataRecord([core.GNode(tr0_name, 1, 2)]),
        ]
        actual = core._find_records_1(
            tr0_gnode, tr0, distances, node_namer, mocked_edit_dist_threshold, max_tag_per_gnode
        )
        self._compare_all_data_records(expected, actual)

        expected = [
            core.DataRecord([core.GNode(tr1_name, 0, 1)]),
            core.DataRecord([core.GNode(tr1_name, 1, 2)]),
        ]
        actual = core._find_records_1(
            tr1_gnode, tr1, distances, node_namer, mocked_edit_dist_threshold, max_tag_per_gnode
        )
        self._compare_all_data_records(expected, actual)

        # Figure 13
        # row 1:  | attr1-v | attr1-v | attr1-v | attr1-v |  <-- obj 1
        # row 2:  | attr2-v | attr2-v | attr2-v | attr2-v |  <-- obj 2
        html_str = """
            <div>
                <table>
                    <tr>
                        <td>Joao</td>
                        <td>25</td>
                        <td>M</td>
                    </tr>
                    <tr>
                        <td>Maria</td>
                        <td>30</td>
                        <td>F</td>
                    </tr>
                </table>
            </div>
        """
        div_root = lxml.html.fromstring(html_str)
        node_namer = core.NodeNamer()
        node_namer.load(div_root)
        table = div_root[0]
        tr0, tr1 = table[0], table[1]
        tr0_gnode = core.GNode(node_namer(table), 0, 1)
        tr1_gnode = core.GNode(node_namer(table), 1, 2)
        tr0_name = node_namer(tr0)
        tr1_name = node_namer(tr1)
        distances = {
            tr0_name: {1: {((0, 1), (1, 2)): close_enough, ((1, 2), (2, 3)): close_enough}},
            tr1_name: {1: {((0, 1), (1, 2)): close_enough, ((1, 2), (2, 3)): close_enough}},
        }

        expected = [core.DataRecord([core.GNode(node_namer(table), 0, 1)])]
        actual = core._find_records_1(
            tr0_gnode, tr0, distances, node_namer, mocked_edit_dist_threshold, max_tag_per_gnode
        )
        self._compare_all_data_records(expected, actual)

        expected = [core.DataRecord([core.GNode(node_namer(table), 1, 2)])]
        actual = core._find_records_1(
            tr1_gnode, tr1, distances, node_namer, mocked_edit_dist_threshold, max_tag_per_gnode
        )
        self._compare_all_data_records(expected, actual)

    def test__find_records_n(self):
        self.fail()

    def test__find_records_n_paper_examples(self):
        self.fail()

    def test_get_data_records_as_node_lists(self):
        self.fail()

    def test__get_node(self):
        self.fail()


class TestNodeNamer(TestCase):
    def test_cleanup_all(self):
        self.fail()

    def test_load(self):
        self.fail()

    def test_call(self):
        self.fail()


class Test(TestCase):
    def test_paint_data_records(self):
        self.fail()
