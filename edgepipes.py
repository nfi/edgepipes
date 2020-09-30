#
# Data pipelines for Edge Computing in Python.
#
# Inspired by Google Media pipelines
#
# Dataflow can be within a "process" and then hook in locally
# But can also be via a "bus" or other communication mechanism
# 
# Example: Draw detections
#
# Input 1. Picture
# Input 2. Detections [...]
#
# They can come in one single combined data-packet och as a picture that should be "annotated"
# with labels
#
import cv2
import sys
import time
from calculators.image import *
from calculators.mqtt import *
from calculators.hand import *
from google.protobuf import text_format
import pipeconfig_pb2
import sched
import importlib
import argparse


def _resolve_class(class_name):
    """Return a class instance based on the string representation"""
    if class_name in globals():
        return globals()[class_name]
    class_info = class_name.rsplit('.', 1)
    if len(class_info) != 2:
        raise PipelineError(f"Could not resolve class name {class_name}")
    try:
        m = importlib.import_module(class_info[0])
        try:
            return getattr(m, class_info[1])
        except AttributeError:
            raise PipelineError(f"Class {class_name} does not exist")
    except ImportError:
        raise PipelineError(f"Could not find module for class {class_name}")


def _add_stream_input_node(stream_data, name, node):
    if name not in stream_data:
        stream_data[name] = []
    stream_data[name].append((node, node.get_input_index(name)))


def _merge_options(mapoptions):
    options = {**mapoptions.doubleOptions, **mapoptions.stringOptions}
    return options


class PipelineError(Exception):
    """Exception raised for errors setting up the edge pipeline."""

    def __init__(self, message):
        super().__init__(message)


class Pipeline:

    def __init__(self):
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.streaming_data = {}
        self.pipeline = []
        self.do_exit = False
        self.run_pipeline = False
        self.run_step = 0

    def add_node(self, calculator, prefix, options, input_streams, output_streams):
        print("calculator", calculator)
        node_class = _resolve_class(calculator)
        n = node_class("Node:" + prefix + ":" + calculator, self.streaming_data, options=options)
        n.set_input_names(input_streams)
        n.set_output_names(output_streams)
        for name in input_streams:
            _add_stream_input_node(self.streaming_data, name, n)
        self.pipeline.append(n)

    # Setup a pipeline based on a configuration
    def setup_pipeline(self, config, options=None, prefix=""):
        if options is None:
            options = {}
        pipe = pipeconfig_pb2.CalculatorGraphConfig()
        text_format.Parse(config, pipe)

        # Should check if this already exists in the config...
        #   map_node_options: { key:"video"; value:"rtsp://192.168.1.237:7447/5c8d2bf990085177ff91c7a2_2" }
        ins = CaptureNode(prefix + "input_video", self.streaming_data, options=options.get('input_video', {}))
        ins.set_input_names([])
        ins.set_output_names([prefix + "input_video"])

        outs = ShowImage(prefix + "output_video", self.streaming_data)
        outs.set_input_names([prefix + "output_video"])
        outs.set_output_names([])
        _add_stream_input_node(self.streaming_data, prefix + "output_video", outs)
        self.pipeline.append(ins)
        for nr, node in enumerate(pipe.node, start=1):
            node_options = _merge_options(node.map_node_options)
            self.add_node(node.calculator, prefix, node_options, list(map(lambda x: prefix + x, node.input_stream)),
                          list(map(lambda x: prefix + x, node.output_stream)))
        self.pipeline.append(outs)
        return self.streaming_data, self.pipeline

    def get_node_by_output(self, outputname):
        return list(filter(lambda x: outputname in x.output, self.pipeline))

    # Running with the main thread - as it make use of CV2s show image.
    def run(self):
        while not self.do_exit:
            if self.run_pipeline or self.run_step > 0:
                # Just process all nodes - they will produce output and process the input.
                for node in self.pipeline:
                    node.process_node()
                time.sleep(0.001)
                self.run_step -= 1
            else:
                # Nothing running at the moment...
                time.sleep(1)
            # CV2 wait-key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                return
            self.scheduler.run()

    def step(self):
        self.run_step = 1

    def start(self):
        self.run_pipeline = True

    def stop(self):
        self.run_pipeline = False

    # I always forget if it is quit or exit - so I have both...
    def quit(self):
        self.do_exit = True

    def exit(self):
        self.do_exit = True


# Either load a pbtxt file or use the default above
if __name__ == "__main__":

    pipeline = Pipeline()

    try:
        args = sys.argv[1:]
        p = argparse.ArgumentParser()
        p.add_argument('--input', dest='input', default=None, help='video stream input')
        p.add_argument('-n', '--dry-run', dest='dry_run', action='store_true', default=False,
                       help='test pipeline setup and exit')
        p.add_argument('pipeline', nargs=1)
        conopts = p.parse_args(args)
    except Exception as e:
        sys.exit(f"Illegal arguments: {e}")

    print(f"Loading pipeline from {conopts.pipeline[0]}")
    try:
        with open(conopts.pipeline[0], "r") as f:
            txt = f.read()
    except FileNotFoundError:
        sys.exit(f"Could not find the pipeline config file {conopts.pipeline[0]}")

    opts = {}
    if conopts.input:
        opts['input_video'] = {'video': conopts.input}

    pipeline.setup_pipeline(txt, options=opts)
    if not conopts.dry_run:
        pipeline.start()
        pipeline.run()
