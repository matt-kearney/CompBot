from interface.py import champ_ids
import numpy as np

gamma = .1

def sigmoid(x):
    return 1 / (1 + np.e ** (-1 * x))


def lane_to_int(lane):
    if lane == 'BOT':
        return 0
    elif lane == 'SUP':
        return 3
    elif lane == 'MID':
        return 2
    elif lane == 'TOP':
        return 4
    elif lane == 'JUN':
        return 1


# Class representing an input neuron
# Each input will have a set number of weights corresponding to different hidden neurons and eventual output
# For each, 0 corresponds with final output, and 1 corresponds with individual match-ups
# BOT/SUP: 2 = bot/sup, 3 = bot/sup/jg
# MID: 2 = mid/jg, 3 = mid/top/jg
# TOP: 2 = top/jg, 3 = mid/top/jg
# JUN: 2 = mid/jg, 3 = top/jg, 4 = mid/top/jg, 5 = bot/sup/jg
class Input:

    def __init__(self, champion, size=3):
        self.champion = champion
        self.value = 0
        self.weights = []
        for a in range(0, size):
            self.weights.append(0)

    def set_input(self, value):
        self.value = value


# A Cluster object corresponds to each role
class Cluster:

    def __init__(self, role):
        self.role = role
        self.inputs = []
        self.value = 0
        if role == "JUN":
            size = 6
        else:
            size = 4
        for champ in champ_ids:
            self.inputs.append(Input(champ, size))
        self.active_neurons = []

    def reset(self):
        self.active_neurons = []

    def add(self, index, value):
        self.active_neurons.append(index)
        self.inputs[index].value = value


class Neuron:

    def __init__(self, clusters):
        self.clusters = clusters
        self.value = 0
        self.weights = []
        self.delta = 0
        self.weight = 0

    def solve(self):
        self.value = 0
        weight = 0
        for cluster in self.clusters:
            for index in cluster.active_neurons:
                self.value += cluster.inputs[index].value * cluster.inputs[index].weights[self.weights[weight]]
            weight += 1
        self.value = sigmoid(self.value)

    # initialize weight indices
    def init_weights(self, clusters):
        if len(clusters) == 1:
            self.weights = [1]
        elif len(clusters) == 2:
            if clusters[0].role == "JUN":
                if clusters[1].role == "MID":
                    self.weights = [2, 2]
                else:
                    self.weights = [3, 2]
            else:
                self.weights = [2, 2]
        elif len(clusters) == 3:
            if clusters[0].role == "BOT":
                self.weights = [3, 5, 3]
            else:
                self.weights = [3, 4, 3]

    def backpropagate(self, output_delta):
        self.weight = self.weight - gamma * output_delta * self.value
        self.delta = self.weight * output_delta
        for c in range(0,len(self.clusters)):
            cluster = self.clusters[c]
            for index in cluster.active_neurons:
                cluster.inputs[index].weights[self.weights[c]] -= gamma * self.delta * cluster.inputs[index].value

class Network:

    def __init__(self):
        # DEFINE CLUSTERS
        self.BOT = Cluster('BOT')
        self.SUP = Cluster('SUP')
        self.MID = Cluster('MID')
        self.TOP = Cluster('TOP')
        self.JUN = Cluster('JUN')

        # DEFINE NEURONS (names are alphabetical order)
        singles = [Neuron([self.BOT]), Neuron([self.SUP]), Neuron([self.MID]), Neuron([self.TOP]), Neuron([self.JUN])]
        doubles = [Neuron([self.BOT, self.SUP]), Neuron([self.JUN, self.MID]), Neuron([self.JUN, self.TOP])]
        triples = [Neuron([self.BOT, self.JUN, self.SUP]), Neuron([self.JUN, self.MID, self.TOP])]

        # DEFINE OUTPUT
        self.output = singles + doubles + triples
        self.lanes = [self.BOT, self.JUN, self.MID, self.SUP, self.TOP]
        self.output_value = 0
        self.delta = 0

    def set_lane_value(self, lane, champ, value):
        self.lanes[lane_to_int(lane)].add(champ_ids[champ], value)

    def solve(self):
        self.output_value = 0
        for lane in self.lanes:
            for a in range(0,2):
                self.output_value += lane.inputs[lane.active_neurons[a]].value * lane.input[lane.active_neurons[a]].weights[0]
        for neuron in self.output:
            self.output_value += neuron.value * neuron.weight
        self.output_value = sigmoid(self.output_value)

    def backpropagate(self, expected):
        self.delta = (self.output_value - expected) * self.output_value * (1 - self.output_value)
        for neuron in self.output:
            neuron.backpropagate(self.delta)
        for lane in self.lanes:
            for a in range(0, 2):
                lane.inputs[lane.active_neurons[a]].weights[0] -= gamma * self.delta * lane.inputs[lane.active_neurons[a]].value