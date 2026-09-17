"""CLI argument parser for auto_updater."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto_updater")
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--source-exe", required=True)
    parser.add_argument("--target-exe", required=True)
    parser.add_argument("--backup-exe", required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--target-version", required=True)
    parser.add_argument("--updated-at", required=True)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--restart", default="true")
    return parser
