
from typing import List, Any
import json

from pylatex import Document, Section, Subsection, Command, LongTable, MultiColumn

from pylatex.utils import italic, NoEscape

from vot.tracker import Tracker
from vot.experiment import Experiment
from vot.analysis import Analysis, Measure, Curve

def extract_measures_table(results):
    table_header = [[], [], []]
    table_data = dict()

    for experiment, eresults in results.items():
        for analysis, aresults in eresults.items():
            descriptions = analysis.describe()

            for i, description in descriptions:
                if description is None:
                    continue
                if isinstance(description, Measure):
                    table_header[0].append(experiment)
                    table_header[1].append(analysis)
                    table_header[2].append(description)

            for tracker, tresult in aresults:
                if not tracker in table_data:
                    table_data[tracker] = list()
                for i, description in enumerate(descriptions):
                    if description is None:
                        continue
                    if isinstance(description, Measure):
                        table_data[tracker].append(aresults[tracker][i])

    return table_header, table_data

def extract_plots(results):
    plots = dict()

    for experiment, eresults in results.items():
        for analysis, aresults in eresults.items():
            descriptions = analysis.describe()

            curves = []
            measures = []

            for i, description in descriptions:
                if description is None:
                    continue
                if isinstance(description, Measure):
                    measures.append(description)
                if isinstance(description, Curve):
                    curves.append(description)

            if len(measures) == 2:
                pass


    return plots

def merge_repeats(objects):
    
    if not objects:
        return []

    repeats = []
    previous = objects[0]
    count = 1

    for o in objects[1:]:
        if o == previous:
            count = count + 1
        else:
            repeats.append((previous, count))
            previous = o
            count = 1

    repeats.append((previous, count))

    return repeats

def generate_json_document(results, filename):

    class StringifyEncoder(json.JSONEncoder):
        def default(self, obj: Any):  # pylint: disable=E0202
            if isinstance(obj, Analysis):
                return obj.name
            if isinstance(obj, Tracker):
                return obj.label
            if isinstance(obj, Experiment):
                return obj.identifier
            return json.JSONEncoder.default(self, obj)

    with open(filename, "w") as fp:
        json.dump(results, fp, indent=2, cls=StringifyEncoder)


def generate_latex_document(results, path, compile=False):

    table_header, table_data = extract_measures_table(results)

    doc = Document(page_numbers=True)

   # Generate data table
    with doc.create(LongTable("l " * len(table_header[2] + 1) )) as data_table:
        data_table.add_hline()
        data_table.add_row([" "] + [ MultiColumn(c[1], data=c[0].identifier) for c in merge_repeats(table_header[0])])
        data_table.add_hline()
        data_table.add_row([" "] + [ MultiColumn(c[1], data=c[0].identifier) for c in merge_repeats(table_header[1])])
        data_table.add_hline()
        data_table.add_row([" "] + [ c.abbreviation for c in table_header[2] ])
        data_table.add_hline()
        data_table.end_table_header()
        data_table.add_hline()

        for tracker, data in table_data.items():
            data_table.add_row([tracker.label] + data)







    doc.generate_pdf("longtable", clean_tex=False)


def generate_html_document(results, path):
    raise NotImplementedError