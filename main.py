#!/usr/bin/python

import argparse

from indoor_router_finder import RouteCalculator, read_and_preprocess_graphml, preprocess_controls


def get_parsed_arguments():
    parser = argparse.ArgumentParser(
        description="Tool to find the fastest or shortest route in indoor orienteering"
    )
    parser.add_argument(
        "--map-image",
        type=str,
        default=None,
        required=True,
        help="Input map used to render the route on"
    )
    parser.add_argument(
        "--node-graph",
        type=str,
        default=None,
        required=True,
        help="File containing a graph of the possible waypoints (currently only yEd graphml)"
    )
    parser.add_argument(
        "--output-directory",
        type=str,
        default=None,
        required=True,
        help="Output path"
    )
    parser.add_argument(
        "--max-routes",
        type=int,
        default=3,
        required=False,
        help="Maximum number of routes to find between two controls"
    )
    parser.add_argument(
        "--control-list",
        type=str,
        default=None,
        required=True,
        help="Comma separated list of control points in a course"
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = get_parsed_arguments()
    adjusted_graphml_string = read_and_preprocess_graphml(args.node_graph)
    course_control_list = preprocess_controls(args.control_list)
    route_calculator = RouteCalculator(adjusted_graphml_string)
    route_calculator.calc_paths(course_control_list, args.max_routes, args.map_image, args.output_directory)
