#!/usr/bin/env python3

import pprint
import ssl

from active_learner import ActiveLearner
from command_line_interface import parse_CLI, create_simulator_params
from data_extraction import get_datasets
from evaluator import *
from datetime import datetime

working_directory = './'


# TODO: copy config file to output too. Also log command line prompt if more complicated


def simulate():
    """
    Main handler for running the simulation program
    Obtains desired parameters from configurations and executions active learner, outputs evaluation results.

    :return:
    """
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context

    # set up output directory
    output_name = str(datetime.now())
    output_directory = working_directory + output_name

    pp = pprint.PrettyPrinter()

    # get desired parameters for training
    arg_names, args = parse_CLI(["DATA", "FEATURE EXTRACTION", "MODEL", "SELECTOR", "STOPPER", "TRAINING", "OUTPUT"])

    params = create_simulator_params(arg_names, args)

    configs = []
    # for each configuration
    for k, param in enumerate(params):
        print()
        print("Executing config {name}, {k}/{n}".format(name=param['name'], k=k+1, n=len(params)))
        pp.pprint(param)

        # make output directory
        output_directory = os.path.join(param['output_path'], output_name)
        if not os.path.isdir(output_directory):
            os.makedirs(output_directory)

        # make folder for each config
        output_path = os.path.join(output_directory, param['name'])
        if not os.path.isdir(output_path):
            os.makedirs(output_path)

        # output config parameters
        output_name = "{path}/{name}.json".format(path=output_path, name="config_parameters")
        with open(output_name, 'w') as f:
            json.dump(param, f, cls=ParamEncoder)

        # get datasets to train the program on
        datasets = get_datasets(*param['data'], output_directory, param['feature_extraction'])
        if len(datasets) == 0:
            continue

        # store program objects for later evaluation
        active_learners = []

        # set randomisation seed
        np.random.seed(0)

        # train for each dataset
        for i, dataset in enumerate(datasets):
            print("\nAnalysing dataset {0} out of {1}...".format(i + 1, len(datasets)))
            data = {'train': datasets[i], 'dev': datasets[i]}
            active_learner = run_model(data, param)
            active_learners.append(active_learner)

        # visualise the overall training results
        evaluators = [AL.evaluator for AL in active_learners]
        ax = visualise_results(evaluators)
        ax.figure.savefig(output_path + '/recall-work.png', dpi=300)

        # visualise and compute output metrics
        output_results(active_learners, output_path, param['output_metrics'])

        # compile config results
        config = Config(param)
        config.update_metrics(active_learners)
        configs.append(config)

    # plot config comparison results
    if len(configs) > 0:
        axs = Config.evaluate_configs(configs)
        for i, ax in enumerate(axs):
            # ax.figure.savefig("{path}/{fig_name}.png".format(path=output_directory, fig_name=configs[0].metrics[i]['name']), dpi=300)
            # ax.write_image("{path}/{fig_name}.png".format(path=output_directory, fig_name=configs[0].metrics[i]['name']))
            ax.write_html("{path}/{fig_name}.html".format(path=output_directory, fig_name=configs[0].metrics[i]['name']))


class Config:
    """
    Helper class for storing evaluation metrics between configuration results
    """
    def __init__(self, param):
        self.metrics = []
        self.param = param
        pass

    def update_metrics(self, active_learners):
        """
        Updates the metrics of the Config object

        :param active_learners: trained active learner object
        :return:
        """
        recalls = []
        work_saves = []
        for AL in active_learners:
            recalls.append(AL.evaluator.recall[-1])
            work_saves.append(AL.evaluator.work_save[-1])

        min_recall = min(recalls)
        mean_recall = sum(recalls) / len(recalls)

        min_work_save = min(work_saves)
        mean_work_save = sum(work_saves) / len(work_saves)

        self.metrics.append({'name': 'min metrics', 'x': ('work save', min_work_save), 'y': ('recall', min_recall)})
        self.metrics.append({'name': 'mean metrics', 'x': ('work save', mean_work_save), 'y': ('recall', mean_recall)})
        return

    @staticmethod
    def evaluate_configs(configs):
        """
        Compile results of different configurations and visualise comparison

        :param configs: Config objects
        :return: axes of the comparative plots
        """
        metrics = []
        axs = []
        for i, metric in enumerate(configs[0].metrics):
            metrics.append({'name': metric['name'], 'x': (metric['x'][0], []), 'y': (metric['y'][0], [])})
            for config in configs:
                metrics[i]['x'][1].append(config.metrics[i]['x'][1])
                metrics[i]['y'][1].append(config.metrics[i]['y'][1])
            # ax = visualise_metric(metrics[i])
            ax = scatter_plot(metrics[i])
            axs.append(ax)
        return axs


def run_model(data, params):
    """
    Creates algorithm objects and runs the active learning program

    :param data: dataset for systematic review labelling
    :param params: input parameters for algorithms and other options for training
    :return: returns the evaluator and stopper objects trained on the dataset
    """
    N = len(data['train'])
    # determine suitable batch size, batch size increases with increases dataset size
    batch_size = int(params['batch_proportion'] * N) + 1

    # create algorithm objects
    model_AL = params['model'][0](*params['model'][1])

    selector = params['selector'][0](batch_size, *params['selector'][1], verbose=params['selector'][2])

    stopper = params['stopper'][0](N, params['confidence'], *params['stopper'][1], verbose=params['stopper'][2])

    # specify evaluator object if desired
    evaluator = params['evaluator'][0](data['train'], verbose=params['evaluator'][1])

    # create active learner
    active_learner = ActiveLearner(model_AL, selector, stopper, batch_size=batch_size, max_iter=1000,
                                   evaluator=evaluator, verbose=params['active_learner'][1])

    # train active learner
    active_learner.train(data['train'])

    return active_learner


class ParamEncoder(json.JSONEncoder):
    def default(self, param):
        return {'module': param.__module__, 'class': param.__name__}


def save_output_text(string, output_path, file_name):
    with open(os.path.join(output_path, file_name), 'w') as f:
        f.write(string)


if __name__ == '__main__':
    simulate()
