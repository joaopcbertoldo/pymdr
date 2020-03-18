from collections import defaultdict, namedtuple, UserList
from typing import Set, List, Dict, Any, Union

import lxml
import lxml.html
import lxml.etree
import Levenshtein

from src.utils import FormatPrinter

NODE_NAME_ATTRIB = "___tag_name___"


class WithBasicFormat(object):
    """Define a basic __format__ with !s, !r and ''."""

    def _extra_format(self, format_spec: str) -> str:
        raise NotImplementedError()

    def __format__(self, format_spec: str) -> str:
        if format_spec == "!s":
            return str(self)
        elif format_spec in ("!r", ""):
            return repr(self)
        else:
            try:
                return self._extra_format(format_spec)
            except NotImplementedError:
                raise TypeError(
                    "unsupported format string passed to {}.__format__".format(
                        type(self).__name__
                    )
                )


class GNode(namedtuple("GNode", ["parent", "start", "end"]), WithBasicFormat):
    """Generalized Node - start/end are indexes of sibling nodes relative to their parent node."""

    def __str__(self):
        return "GN({start:>2}, {end:>2})".format(
            start=self.start, end=self.end
        )

    def __len__(self):
        return self.size

    def _extra_format(self, format_spec):
        if format_spec == "!S":
            return "GN({parent}, {start:>2}, {end:>2})".format(
                parent=self.parent, start=self.start, end=self.end
            )
        else:
            raise NotImplementedError()

    @property
    def size(self):
        return self.end - self.start


# noinspection PyAbstractClass
class GNodePair(namedtuple("GNodePair", ["left", "right"]), WithBasicFormat):
    """Generalized Node Pair - pair of adjacent GNodes, used for stocking the edit distances between them."""

    def __str__(self):
        return "{left:!s} - {right:!s}".format(
            left=self.left, right=self.right
        )


# noinspection PyArgumentList
class DataRegion(
    namedtuple(
        "DataRegion",
        ["parent", "gnode_size", "first_gnode_start_index", "n_nodes_covered"],
    ),
    WithBasicFormat,
):
    """Data Region - a continuous sequence of GNode's."""

    def _extra_format(self, format_spec):
        if format_spec == "!S":
            return "DR({0}, {1}, {2}, {3})".format(
                self.parent,
                self.gnode_size,
                self.first_gnode_start_index,
                self.n_nodes_covered,
            )
        else:
            raise NotImplementedError()

    def __str__(self):
        return "DR({0}, {1}, {2})".format(
            self.gnode_size, self.first_gnode_start_index, self.n_nodes_covered
        )

    def __contains__(self, child_index):
        """todo(doc)"""
        msg = (
            "DataRegion contains the indexes of a node relative to its parent list of children. "
            "Type `{}` not supported.".format(type(child_index).__name__)
        )
        assert isinstance(child_index, int), msg
        return (
            self.first_gnode_start_index
            <= child_index
            <= self.last_covered_tag_index
        )

    def __iter__(self):
        self._iter_i = 0
        return self

    def __next__(self):
        if self._iter_i < self.n_gnodes:
            start = (
                self.first_gnode_start_index + self._iter_i * self.gnode_size
            )
            end = start + self.gnode_size
            gnode = GNode(self.parent, start, end)
            self._iter_i += 1
            return gnode
        else:
            raise StopIteration

    @classmethod
    def empty(cls):
        return cls(None, None, None, 0)

    @classmethod
    def binary_from_last_gnode(cls, gnode: GNode):
        """(Joao: I know the name is confusing...) It is the DR of 2 GNodes where the last one is `gnode`."""
        gnode_size = gnode.end - gnode.start
        return cls(
            gnode.parent, gnode_size, gnode.start - gnode_size, 2 * gnode_size
        )

    @property
    def is_empty(self):
        return self[0] is None

    @property
    def n_gnodes(self):
        return self.n_nodes_covered // self.gnode_size

    @property
    def last_covered_tag_index(self):
        return self.first_gnode_start_index + self.n_nodes_covered - 1

    def extend_one_gnode(self):
        return self.__class__(
            self.parent,
            self.gnode_size,
            self.first_gnode_start_index,
            self.n_nodes_covered + self.gnode_size,
        )


# noinspection PyAbstractClass
class DataRecord(UserList, WithBasicFormat):
    def __hash__(self):
        return hash(tuple(self))

    def __repr__(self):
        return "DataRecord({})".format(
            ", ".join([repr(gn) for gn in self.data])
        )

    def __str__(self):
        return "DataRecord({})".format(
            ", ".join([str(gn) for gn in self.data])
        )


class MDRVerbosity(
    namedtuple(
        "MDRVerbosity",
        "compute_distances find_data_regions identify_data_records",
    )
):
    @classmethod
    def absolute_silent(cls):
        return cls(None, None, None)

    @property
    def is_absolute_silent(self):
        return any(val is None for val in self)

    @classmethod
    def silent(cls):
        return cls(False, False, False)

    @classmethod
    def only_compute_distances(cls):
        return cls(True, False, False)

    @classmethod
    def only_find_data_regions(cls):
        return cls(False, True, False)

    @classmethod
    def only_identify_data_records(cls):
        return cls(False, False, True)


class MDREditDistanceThresholds(
    namedtuple(
        "MDREditDistanceThresholds",
        ["data_region", "find_records_1", "find_records_2"],
    )
):
    @classmethod
    def all_equal(cls, threshold):
        return cls(threshold, threshold, threshold)


# todo(doc): add reference to this
DEFAULT_MDR_EDIT_DISTANCE_THRESHOLD = MDREditDistanceThresholds.all_equal(0.3)
DEFAULT_MDR_MAX_TAGS_PER_GNODE = 10
DEFAULT_MDR_VERBOSITY = MDRVerbosity.absolute_silent()


class UsedMDRException(Exception):
    default_message = "This MDR instance has already been used. Please instantiate another one."

    def __init__(self):
        super(Exception, self).__init__(self.default_message)


# todo(improvement) change the other naming method to use this
class NodeNamer(object):
    """todo(doc)"""

    def __init__(self):
        self.tag_counts = defaultdict(int)
        self.map = {}

    def __call__(self, node, *args, **kwargs):
        if NODE_NAME_ATTRIB in node.attrib:
            return node.attrib[NODE_NAME_ATTRIB]
        # each tag is named sequentially
        tag = node.tag
        tag_sequential = self.tag_counts[tag]
        self.tag_counts[tag] += 1
        node_name = "{0}-{1:0>5}".format(tag, tag_sequential)
        node.set(NODE_NAME_ATTRIB, node_name)
        return node_name

    @staticmethod
    def cleanup_tag_name(node):
        del node.attrib[NODE_NAME_ATTRIB]


# noinspection PyArgumentList
class MDR:
    """
    Notation:
        gn = gnode = generalized node
        dr = data region
    """

    MINIMUM_DEPTH = 3
    DEBUG_FORMATTER = FormatPrinter(
        {float: ".2f", GNode: "!s", GNodePair: "!s", DataRegion: "!s"}
    )

    def __init__(
        self,
        max_tag_per_gnode: int = DEFAULT_MDR_MAX_TAGS_PER_GNODE,
        edit_distance_threshold: MDREditDistanceThresholds = DEFAULT_MDR_EDIT_DISTANCE_THRESHOLD,
        verbose: MDRVerbosity = DEFAULT_MDR_VERBOSITY,
    ):
        self.max_tag_per_gnode = max_tag_per_gnode
        self.edit_distance_threshold = edit_distance_threshold
        self._verbose = verbose
        self._phase = None
        self._used = False

        self.distances = {}
        self.node_namer = NodeNamer()
        # {node_name(str): set(GNode)}  only retains the max data regions
        self.data_regions = {}
        # retains all of them for debug purposes
        self._all_data_regions_found = defaultdict(set)
        self._checked_gnode_pairs = defaultdict(set)
        self.data_records = list()

    def _debug(self, msg: str, tabs: int = 0, force: bool = False):
        if self._verbose.is_absolute_silent:
            return

        if self._verbose[self._phase] or force:
            if type(msg) == str:
                print(tabs * "\t" + msg)
            else:
                self.DEBUG_FORMATTER.pprint(msg)

    def _debug_phase(self, phase: int):
        if self._phase is not None:
            title = " END PHASE {} ({}) ".format(
                MDRVerbosity._fields[self._phase].upper(), self._phase
            )
            self._debug(">" * 20 + title + "<" * 20 + "\n\n", force=True)

        self._phase = phase
        if self._phase <= 2:
            title = " START PHASE {} ({}) ".format(
                MDRVerbosity._fields[self._phase].upper(), self._phase
            )
            self._debug(">" * 20 + title + "<" * 20, force=True)

    @staticmethod
    def depth(node):
        d = 0
        while node is not None:
            d += 1
            node = node.getparent()
        return d - 1

    @staticmethod
    def nodes_to_string(list_of_nodes: List[lxml.html.HtmlElement]) -> str:
        return " ".join(
            [
                lxml.etree.tostring(child).decode("utf-8").strip()
                for child in list_of_nodes
            ]
        )

    def __call__(self, root):
        if self._used:
            raise UsedMDRException()
        self._used = True

        self._debug_phase(0)
        self._compute_distances(root)

        self._debug_phase(1)
        self._find_data_regions(root)

        self._checked_gnode_pairs = dict(self._checked_gnode_pairs)
        self._all_data_regions_found = dict(self._all_data_regions_found)

        self._debug_phase(2)

        def get_node(node_name):
            tag = node_name.split("-")[0]
            # todo add some security stuff here???
            node = root.xpath(
                "//{tag}[@___tag_name___='{node_name}']".format(
                    tag=tag, node_name=node_name
                )
            )[0]
            return node

        self._find_data_records(get_node)

        self._debug_phase(3)
        # todo cleanup attributes ???

        return self.data_records

    def _compute_distances(self, node):

        # !!! ATTENTION !!! this modifies the input HTML element by adding an attribute
        # todo: remember, in the last phase, to clear the `TAG_NAME_ATTRIB` from all tags
        node_name = self.node_namer(node)
        node_depth = MDR.depth(node)
        self._debug(
            "in _compute_distances of `{}` (depth={})".format(
                node_name, node_depth
            )
        )

        if node_depth >= MDR.MINIMUM_DEPTH:

            # get all possible distances of the n-grams of children
            # {gnode_size: {GNode: float}}
            distances = self._compare_combinations(node.getchildren())

        else:
            self._debug(
                "skipped (less than min depth = {})".format(
                    self.MINIMUM_DEPTH
                ),
                1,
            )
            distances = None

        self.distances[node_name] = distances

        for child in node:
            self._compute_distances(child)

    def _compare_combinations(
        self, node_list: List[lxml.html.HtmlElement]
    ) -> Dict[int, Dict[GNode, float]]:
        """
        Notation: gnode = "generalized node"
        :returns
            {gnode_size: {GNode: float}}
        """

        self._debug("in _compare_combinations")

        if not node_list:
            self._debug("empty list --> return {}")
            return {}

        # {gnode_size: {GNode: float}}
        distances = defaultdict(dict)
        n_nodes = len(node_list)
        parent = node_list[0].getparent()
        parent_name = self.node_namer(parent)
        self._debug("n_nodes: {}".format(n_nodes))

        # 1) for (i = 1; i <= K; i++)  /* start from each node */
        for starting_tag in range(1, self.max_tag_per_gnode + 1):
            self._debug("starting_tag (i): {}".format(starting_tag), 1)

            # 2) for (j = i; j <= K; j++) /* comparing different combinations */
            for gnode_size in range(
                starting_tag, self.max_tag_per_gnode + 1
            ):  # j
                self._debug("gnode_size (j): {}".format(gnode_size), 2)

                # 3) if NodeList[i+2*j-1] exists then
                there_are_pairs_to_look = (
                    starting_tag + 2 * gnode_size - 1
                ) < n_nodes + 1
                if there_are_pairs_to_look:  # +1 for pythons open set notation
                    self._debug(">>> if 1: there_are_pairs_to_look <<<", 3)

                    # 4) St = i;
                    left_gnode_start = starting_tag - 1  # st

                    # 5) for (k = i+j; k < Size(NodeList); k+j)
                    for right_gnode_start in range(
                        starting_tag + gnode_size - 1, n_nodes, gnode_size
                    ):  # k
                        self._debug(
                            "left_gnode_start (st): {}".format(
                                left_gnode_start
                            ),
                            4,
                        )
                        self._debug(
                            "right_gnode_start (k): {}".format(
                                right_gnode_start
                            ),
                            4,
                        )

                        # 6)  if NodeList[k+j-1] exists then
                        right_gnode_exists = (
                            right_gnode_start + gnode_size < n_nodes + 1
                        )
                        if right_gnode_exists:
                            self._debug(">>> if 2: right_gnode_exists <<<", 5)

                            # todo(improvement): avoid recomputing strings?
                            # todo(improvement): avoid recomputing edit distances?
                            # todo(improvement): check https://pypi.org/project/strsim/ ?

                            # NodeList[St..(k-1)]
                            left_gnode = GNode(
                                parent_name,
                                left_gnode_start,
                                right_gnode_start,
                            )
                            left_gnode_nodes = node_list[
                                left_gnode.start : left_gnode.end
                            ]
                            left_gnode_str = MDR.nodes_to_string(
                                left_gnode_nodes
                            )

                            # NodeList[St..(k-1)]
                            right_gnode = GNode(
                                parent_name,
                                right_gnode_start,
                                right_gnode_start + gnode_size,
                            )
                            right_gnode_nodes = node_list[
                                right_gnode.start : right_gnode.end
                            ]
                            right_gnode_str = MDR.nodes_to_string(
                                right_gnode_nodes
                            )

                            # 7) EditDist(NodeList[St..(k-1), NodeList[k..(k+j-1)])
                            edit_distance = Levenshtein.ratio(
                                left_gnode_str, right_gnode_str
                            )

                            gnode_pair = GNodePair(left_gnode, right_gnode)
                            self._debug(
                                "gnode pair = dist: {0:!s} = {1:.2f}".format(
                                    gnode_pair, edit_distance
                                ),
                                5,
                            )

                            # {gnode_size: {GNode: float}}
                            distances[gnode_size][gnode_pair] = edit_distance

                            # 8) St = k+j
                            left_gnode_start = right_gnode_start
                        else:
                            self._debug("skipped, right node doesn't exist", 5)
                else:
                    self._debug("skipped, there are no pairs to look", 3)

        return dict(distances)

    def _find_data_regions(self, node):
        node_name = self.node_namer(node)
        node_depth = MDR.depth(node)

        self._debug("in _find_data_regions of `{}`".format(node_name))

        # 1) if TreeDepth(Node) => 3 then
        if node_depth >= MDR.MINIMUM_DEPTH:

            # 2) Node.DRs = IdenDRs(1, Node, K, T);
            node_name = self.node_namer(node)
            n_children = len(node)
            distances = self.distances.get(node_name)
            # todo(prod) remove this
            checked_pairs = self._checked_gnode_pairs[node_name]
            data_regions = self._identify_data_regions(
                start_index=0,
                node_name=node_name,
                n_children=n_children,
                distances=distances,
                checked_pairs=checked_pairs,
            )
            self.data_regions[node_name] = data_regions
            self._debug("`{}`: data regions found:".format(node_name), 1)
            self._debug(self.data_regions[node_name])

            # 3) tempDRs = ∅;
            temp_data_regions = set()

            # 4) for each Child ∈ Node.Children do
            for child in node.getchildren():
                # 5) FindDRs(Child, K, T);
                self._find_data_regions(child)

                # 6) tempDRs = tempDRs ∪ UnCoveredDRs(Node, Child);
                uncovered_data_regions = self._uncovered_data_regions(
                    node, child
                )
                temp_data_regions = temp_data_regions | uncovered_data_regions

            self._debug("`{}`: temp data regions: ".format(node_name), 1)
            self._debug(temp_data_regions)

            # 7) Node.DRs = Node.DRs ∪ tempDRs
            self.data_regions[node_name] |= temp_data_regions

            self._debug(
                "`{}`: data regions found (FINAL):".format(node_name), 1
            )
            self._debug(self.data_regions[node_name])

        else:
            self._debug(
                "skipped (less than min depth = {}), calling recursion on children...\n".format(
                    self.MINIMUM_DEPTH
                ),
                1,
            )
            for child in node.getchildren():
                self._find_data_regions(child)

    def _identify_data_regions(
        self, start_index, node_name, n_children, distances, checked_pairs
    ):

        self._debug("in _identify_data_regions node: {}".format(node_name))
        self._debug("start_index:{}".format(start_index), 1)

        if not distances:
            self._debug("no distances, returning empty set")
            return set()

        # 1 maxDR = [0, 0, 0];
        max_dr = DataRegion.empty()
        current_dr = DataRegion.empty()

        # 2 for (i = 1; i <= K; i++) /* compute for each i-combination */
        for gnode_size in range(1, self.max_tag_per_gnode + 1):
            self._debug("gnode_size (i): {}".format(gnode_size), 2)

            # 3 for (f = start; f <= start+i; f++) /* start from each node */
            # for start_gnode_start_index in range(start_index, start_index + gnode_size + 1):
            for first_gn_start_idx in range(
                start_index, start_index + gnode_size
            ):
                self._debug(
                    "first_gn_start_idx (f): {}".format(first_gn_start_idx), 3
                )

                # 4 flag = true;
                dr_has_started = False

                # 5 for (j = f; j < size(Node.Children); j+i)
                # for left_gnode_start in range(start_node, len(node) , gnode_size):
                for last_gn_start_idx in range(
                    # start_gnode_start_index, len(node) - gnode_size + 1, gnode_size
                    first_gn_start_idx + gnode_size,
                    n_children - gnode_size + 1,
                    gnode_size,
                ):
                    self._debug(
                        "last_gn_start_idx (j): {}".format(last_gn_start_idx),
                        4,
                    )

                    # 6 if Distance(Node, i, j) <= T then
                    gn_last = GNode(
                        node_name,
                        last_gn_start_idx,
                        last_gn_start_idx + gnode_size,
                    )
                    gn_before_last = GNode(
                        node_name,
                        last_gn_start_idx - gnode_size,
                        last_gn_start_idx,
                    )
                    gn_pair = GNodePair(gn_before_last, gn_last)
                    distance = distances[gnode_size][gn_pair]
                    checked_pairs.add(gn_pair)

                    self._debug(
                        "gn_pair (bef last, last): {!s} = {:.2f}".format(
                            gn_pair, distance
                        ),
                        5,
                    )

                    if distance <= self.edit_distance_threshold.data_region:

                        self._debug(
                            "dist passes the threshold!".format(distance), 6
                        )

                        # 7 if flag=true then
                        if not dr_has_started:

                            self._debug(
                                "it is the first pair, init the `current_dr`...".format(
                                    distance
                                ),
                                6,
                            )

                            # 8 curDR = [i, j, 2*i];
                            # current_dr = DataRegion(gnode_size, first_gn_start_idx - gnode_size, 2 * gnode_size)
                            # current_dr = DataRegion(gnode_size, first_gn_start_idx, 2 * gnode_size)
                            current_dr = DataRegion.binary_from_last_gnode(
                                gn_last
                            )

                            self._debug("current_dr: {}".format(current_dr), 6)

                            # 9 flag = false;
                            dr_has_started = True

                        # 10 else curDR[3] = curDR[3] + i;
                        else:
                            self._debug(
                                "extending the DR...".format(distance), 6
                            )
                            # current_dr = DataRegion(
                            #     current_dr[0], current_dr[1], current_dr[2] + gnode_size
                            # )
                            current_dr = current_dr.extend_one_gnode()
                            self._debug("current_dr: {}".format(current_dr), 6)

                    # 11 elseif flag = false then Exit-inner-loop;
                    elif dr_has_started:
                        self._debug(
                            "above the threshold, breaking the loop...", 6
                        )
                        break

                # 13 if (maxDR[3] < curDR[3]) and (maxDR[2] = 0 or (curDR[2]<= maxDR[2]) then
                # todo(improvement) add a criteria that checks the avg distance when
                #  n_nodes_covered is the same and it starts at the same node
                current_is_strictly_larger = (
                    max_dr.n_nodes_covered < current_dr.n_nodes_covered
                )
                current_starts_at_same_node_or_before = (
                    max_dr.is_empty
                    or current_dr.first_gnode_start_index
                    <= max_dr.first_gnode_start_index
                )

                if (
                    current_is_strictly_larger
                    and current_starts_at_same_node_or_before
                ):
                    self._debug(
                        "current DR is bigger than max! replacing...", 3
                    )

                    # 14 maxDR = curDR;
                    self._debug(
                        "old max_dr: {}, new max_dr: {}".format(
                            max_dr, current_dr
                        ),
                        3,
                    )
                    max_dr = current_dr
                self._debug("max_dr: {}".format(max_dr), 2)
        self._debug("max_dr: {}\n".format(max_dr))

        # 16 if ( maxDR[3] != 0 ) then
        if not max_dr.is_empty:

            # 17 if (maxDR[2]+maxDR[3]-1 != size(Node.Children)) then
            last_covered_idx = max_dr.last_covered_tag_index
            self._debug(
                "max_dr.last_covered_tag_index: {}".format(last_covered_idx)
            )

            if last_covered_idx < n_children - 1:
                self._debug("calling recursion! \n")

                # 18 return {maxDR} ∪ IdentDRs(maxDR[2]+maxDR[3], Node, K, T)
                return {max_dr} | self._identify_data_regions(
                    start_index=last_covered_idx + 1,
                    node_name=node_name,
                    n_children=n_children,
                    distances=distances,
                    checked_pairs=checked_pairs,
                )

            # 19 else return {maxDR}
            else:
                self._debug("returning {{max_dr}}")
                return {max_dr}

        # 21 return ∅;
        self._debug("max_dr is empty, returning empty set")
        return set()

    def _uncovered_data_regions(self, node, child):
        node_name = self.node_namer(node)
        node_drs = self.data_regions[node_name]
        children_names = [self.node_namer(c) for c in node.getchildren()]
        child_name = self.node_namer(child)
        child_idx = children_names.index(child_name)

        # 1) for each data region DR in Node.DRs do
        for dr in node_drs:
            # 2) if Child in range DR[2] .. (DR[2] + DR[3] - 1) then
            if child_idx in dr:
                # todo(unittest) test case where child idx is in the limit
                # 3) return null
                return set()
        # 4) return Child.DRs
        return self.data_regions[child_name]

    def _find_data_records(self, get_node_by_name: callable):
        self._debug("in _find_data_records")

        all_data_regions: Set[DataRegion] = set.union(
            *self.data_regions.values()
        )
        self._debug(
            "total nb of data regions to check: {}".format(
                len(all_data_regions)
            )
        )

        for dr in all_data_regions:
            self._debug("data region: {:!S}".format(dr), 1)

            method = (
                self._find_records_1
                if dr.gnode_size == 1
                else self._find_records_n
            )
            self._debug("selected method: `{}`".format(method.__name__), 2)
            gnode: GNode
            for gnode in dr:
                method(gnode, get_node_by_name)

        # todo: add the retrieval of data records out of data regions (technical report)

    def _find_records_1(self, gnode: GNode, get_node_by_name: callable):
        """Finding data records in a one-component generalized node."""
        self._debug("in `_find_records_1` for gnode `{:!S}`".format(gnode), 2)

        parent_node = get_node_by_name(gnode.parent)
        node = parent_node[gnode.start]
        node_name = self.node_namer(node)

        node_children_distances = self.distances[node_name].get(1, None)

        if node_children_distances is None:
            self._debug(
                "node doesn't have children distances, returning...", 3
            )
            return

            # 1) If all children nodes of G are similar
        # it is not well defined what "all .. similar" means - I consider that "similar" means "edit_dist < TH"
        #       hyp 1: it means that every combination 2 by 2 is similar
        #       hyp 2: it means that all the computed edit distances (every sequential pair...) is similar
        # for the sake of practicality and speed, I'll choose the hypothesis 2
        all_children_are_similar = all(
            d <= self.edit_distance_threshold.find_records_1
            for d in node_children_distances.values()
        )

        # 2) AND G is not a data table row then
        node_is_table_row = node.tag == "tr"

        if all_children_are_similar and not node_is_table_row:
            self._debug("its children are data records", 3)
            # 3) each child node of R is a data record
            for i in range(len(node)):
                self.data_records.append(
                    DataRecord([GNode(node_name, i, i + 1)])
                )

        # 4) else G itself is a data record.
        else:
            self._debug("it is a data record itself", 3)
            self.data_records.append(DataRecord([gnode]))

        # todo(unittest): debug this implementation with examples in the technical paper

    def _find_records_n(self, gnode: GNode, get_node_by_name: callable):
        """Finding data records in an n-component generalized node."""
        self._debug("in `_find_records_n` for gnode `{:!S}`".format(gnode), 2)

        parent_node: lxml.html.HtmlElement = get_node_by_name(gnode.parent)
        nodes = parent_node[gnode.start : gnode.end]
        numbers_children = [len(n) for n in nodes]
        childrens_distances = [
            self.distances[self.node_namer(n)].get(1, None) for n in nodes
        ]

        all_have_same_nb_children = len(set(numbers_children)) == 1
        childrens_are_similar = None not in childrens_distances and all(
            all(
                d <= self.edit_distance_threshold.find_records_n
                for d in child_distances
            )
            for child_distances in childrens_distances
        )

        # 1) If the children nodes of each node in G are similar
        # 1...)   AND each node also has the same number of children then
        if not (all_have_same_nb_children and childrens_are_similar):

            # 3) else G itself is a data record.
            self.data_records.append(DataRecord([gnode]))

        else:
            # 2) The corresponding children nodes of every node in G form a non-contiguous object description
            n_children = numbers_children[0]
            for i in range(n_children):
                self.data_records.append(
                    DataRecord(
                        [GNode(self.node_namer(n), i, i + 1) for n in nodes]
                    )
                )
            # todo(unittest) check a case like this

        # todo(unittest): debug this implementation

    def get_data_records_as_node_lists(
        self, root: lxml.html.HtmlElement
    ) -> List[List[List[lxml.html.HtmlElement]]]:
        def get_node(node_name):
            tag = node_name.split("-")[0]
            # todo add some security stuff here???
            node = root.xpath(
                "//{tag}[@___tag_name___='{node_name}']".format(
                    tag=tag, node_name=node_name
                )
            )[0]
            return node

        # return [[get_node(gn.parent)[gn.start:gn.end] for gn in dr] for dr in self.data_records]
        return [
            [get_node(gn.parent)[gn.start : gn.end] for gn in data_record]
            for data_record in self.data_records
        ]
