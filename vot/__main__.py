
import os
import argparse
import traceback
import logging

from vot.tracker import load_trackers
from vot.stack import resolve_stack

class EnvDefault(argparse.Action):
    def __init__(self, envvar, required=True, default=None, separator=None, **kwargs):
        if not default and envvar:
            if envvar in os.environ:
                default = os.environ[envvar]
        if separator:
            default = default.split(separator)
        if required and default:
            required = False
        self.separator = separator
        super(EnvDefault, self).__init__(default=default, required=required,
                                         **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if self.separator:
            values = values.split(self.separator)
        setattr(namespace, self.dest, values)

def do_test(config, logger):
    from vot.dataset.dummy import DummySequence
    trackers = load_trackers(config.registry)

    if not config.tracker in trackers:
        logger.error("Tracker does not exist")
        return

    tracker = trackers[config.tracker]

    logger.info("Generating dummy sequence")

    sequence = DummySequence()

    logger.info("Obtaining runtime for tracker %s", tracker.identifier)

    runtime = tracker.runtime()

    logger.info("Initializing tracker")

    runtime.initialize(sequence.frame(0), sequence.groundtruth(0))

    for i in range(1, sequence.length-1):
        logger.info("Updating on frame %d/%d", i, sequence.length-1)
        runtime.update(sequence.frame(i))

    logger.info("Test concluded successfuly")

def do_workspace(config, logger):
    
    from vot.workspace import initialize_workspace

    stack = resolve_stack(config.stack)

    if not stack:
        logger.error("Stack not found")
        return

    default_config = dict(stack=config.stack, registry=["."])

    initialize_workspace(config.workspace, default_config)

    logger.info("Initialized workspace in '%s'", config.workspace)

    if hasattr(stack, "dataset"):
        logger.info("Stack has a dataset attached, downloading bundle '%s'", stack.dataset)

        from vot.dataset import download_vot_dataset
        download_vot_dataset(stack.dataset, os.path.join(config.workspace, "sequences"))

        logger.info("Download completed")

def do_evaluate(config, logger):
    
    from vot.workspace import Workspace

    workspace = Workspace(config.workspace)

    logger.info("Loaded workspace in '%s'", config.workspace)

    registry = load_trackers(workspace.registry + config.registry)

    logger.info("Found data for %d trackers", len(registry))

    try:
        trackers = [registry[t.strip()] for t in config.trackers.split(",")]
    except KeyError as ke:
        logger.error("Tracker not found %s", str(ke))
        return

    for tracker in trackers:
        logger.info(" |= > Evaluating tracker %s", tracker.identifier)
        for experiment in workspace.stack:
            logger.info(" |== > Running experiment %s", experiment.identifier)
            for sequence in workspace.dataset:
                logger.info(" |=== > Sequence %s", sequence.name)
                experiment.execute(tracker, sequence, workspace.results(tracker, experiment, sequence))

    logger.info("Evaluation concluded successfuly")


def do_analysis(config, logger):
    pass

def do_pack(config, logger):

    import zipfile
    from shutil import copyfileobj
    from datetime import datetime
    from vot.workspace import Workspace

    workspace = Workspace(config.workspace)

    logger.info("Loaded workspace in '%s'", config.workspace)

    registry = load_trackers(workspace.registry + config.registry)

    logger.info("Found data for %d trackers", len(registry))

    try:
        tracker = registry[config.tracker]
    except KeyError as ke:
        logger.error("Tracker not found %s", str(ke))
        return

    logger.info("Packaging results for tracker %s", tracker.identifier)

    all_files = []
    can_finish = True

    for experiment in workspace.stack:
        logger.info(" |= > Scanning experiment %s", experiment.identifier)
        for sequence in workspace.dataset:
            results = workspace.results(tracker, experiment, sequence)
            complete, files = experiment.scan(tracker, sequence, results)
            all_files.extend([(f, experiment.identifier, sequence.name, results) for f in files])
            if not complete:
                logger.error(" X= > Results are not complete for experiment %s, sequence %s", experiment.identifier, sequence.name) 
                can_finish = False

    if not can_finish:
        logger.error("Unable to continue, experiments not complete")
        return

    logger.info("Collected %d files, compressing to archive ...", len(all_files))

    archive_name = "{}_{:%Y-%m-%dT%H:%M:%S.%f%z}".format(tracker.identifier, datetime.now())

    with zipfile.ZipFile(archive_name, 'w') as archive:
        for f in all_files:
            with archive.open(os.path.join(f[1], f[2], f)) as fout, f[3].read(f[0]) as fin:
                copyfileobj(fin, fout)

    logger.info("Result packaging successful, archive available in %s", archive_name)


def main():
    logger = logging.getLogger("vot")
    logger.addHandler(logging.StreamHandler())

    parser = argparse.ArgumentParser(description='VOT Toolkit Command Line Utility', prog="vot")
    parser.add_argument("--debug", "-d", default=False, help="Backup backend", required=False, action='store_true')
    parser.add_argument("--registry", default=".", help='Tracker registry paths', required=False, action=EnvDefault, \
        separator=os.path.pathsep, envvar='VOT_REGISTRY')
    #parser.add_argument("--database", default=".", help='Global sequence database', required=False)

    subparsers = parser.add_subparsers(help='commands', dest='action', title="Commands")

    test_parser = subparsers.add_parser('test', help='Test a tracker integration on a synthetic sequence')
    test_parser.add_argument("tracker", help='Tracker identifier')
    test_parser.add_argument("--visualize", "-g", default=False, help='Visualize results of the test session')

    workspace_parser = subparsers.add_parser('workspace', help='Setup a new workspace and download data')
    workspace_parser.add_argument("--workspace", default=".", help='Workspace path')
    workspace_parser.add_argument("stack", help='Experiment stack')

    evaluate_parser = subparsers.add_parser('evaluate', help='Evaluate one or more trackers in a given workspace')
    evaluate_parser.add_argument("trackers", nargs='?', default=None, help='Tracker identifiers')
    evaluate_parser.add_argument("--force", "-f", default=False, help="Force rerun of the entire evaluation", required=False)
    evaluate_parser.add_argument("--workspace", default=".", help='Workspace path')

    analysis_parser = subparsers.add_parser('analysis', help='Run interactive analysis')
    analysis_parser.add_argument("--workspace", default=".", help='Workspace path')

    pack_parser = subparsers.add_parser('pack', help='Package results for submission')
    pack_parser.add_argument("--workspace", default=".", help='Workspace path')
    pack_parser.add_argument("tracker", help='Tracker identifier')

    try:

        args = parser.parse_args()

        if args.debug:
            logger.setLevel(logging.DEBUG)

        if args.action == "test":
            do_test(args, logger)
        elif args.action == "workspace":
            do_workspace(args, logger)
        elif args.action == "evaluate":
            do_evaluate(args, logger)
        elif args.action == "analyze":
            do_analysis(args, logger)
        elif args.action == "pack":
            do_pack(args, logger)
        else:
            parser.print_help()

    except argparse.ArgumentError:
        traceback.print_exc()


    exit(0)

if __name__ == '__main__':
    main()
