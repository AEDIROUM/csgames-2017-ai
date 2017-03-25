import random

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.protocols.basic import LineReceiver

from hockey.action import Action

import re
import numpy as np
from itertools import product

class HockeyClient(LineReceiver, object):
    def __init__(self, name, debug):
        self.name = name
        self.debug = debug

        # state
        self.grid = np.zeros((11, 11))
        self.edge_taken = np.zeros((11, 11, 11, 11))
        self.ball_position = None
        self.goal = None
        self.blacklist = [(0, 0), (0, 10), (10, 0), (10, 10)]

        # borders
        for i in range(10):
            if i != 4 and i != 6:
                self.edge_taken[(i, 0)][(i + 1, 0)]
        for j in range(10):
            if j != 4 and j != 6:
                self.edge_taken[(i, 0)][(i + 1, 0)]

    def connectionMade(self):
        self.sendLine(self.name)

    def sendLine(self, line):
        super(HockeyClient, self).sendLine(line.encode('UTF-8'))

    def lineReceived(self, line):
        line = line.decode('UTF-8')

        if self.debug:
            print('Server said:', line)
            print(self.grid)

        match = re.match(r'ball is at \((\d+), (\d+)\) - \d+', line)
        if match:
            pos = int(match.group(1)), int(match.group(2))
            self.ball_position = pos
            self.grid[pos] = True
            return

        match = re.match(r'your goal is (\w+) - \d+', line)
        if match:
            self.goal = match.group(1)
            if self.goal == 'north':
                self.blacklist += [(0, 5), (1, 5), (1, 3), (1, 4), (1, 6), (1, 7)]
            else:
                self.blacklist += [(10, 5), (9, 5), (9, 3), (9, 4), (9, 6), (9, 7)]

            #print(self.blacklist)
            return

        match = re.match(r'.* did go (.*) - \d+', line)
        if match:
            dx, dy = Action.move[(match.group(1))]
            new_ball_position = self.ball_position[0] + dy, self.ball_position[1] + dx
            self.grid[new_ball_position] = True
            self.edge_taken[self.ball_position][new_ball_position] = True
            self.edge_taken[new_ball_position][self.ball_position] = True
            self.ball_position = new_ball_position
            return

        if re.match(r'.* won a goal was made - \d+', line):
            return # fin de la partie

        if '{} is active player'.format(self.name) in line or 'invalid move' in line:
            self.sendLine(self.play_game())

    def neighborhood(self, position):
        for edge, delta in Action.move.items():
            dx, dy = delta
            pos = position[0] + dy, position[1] + dx
            if 0 <= pos[0] <= 10 and 0 <= pos[1] <= 10:
                yield edge, pos

    def valid_neighborhood(self, position):
        for neighbor in self.neighborhood(position):
            if not (self.edge_taken[position][neighbor[1]] and neighbor[1] in self.blacklist):
                yield neighbor

class RandomHockeyClient(HockeyClient):
    def play_game(self):
        return random.choice([move for move, pos in self.valid_neighborhood(self.ball_position)])

class GoodHockeyClient(HockeyClient):
    def play_game(self):
        print(self.ball_position)
        print(list(self.neighborhood(self.ball_position)))
        return Action.from_number(random.randint(0, 7))

class ClientFactory(protocol.ClientFactory):
    def __init__(self, name, debug):
        self.name = name
        self.debug = debug

    def buildProtocol(self, addr):
        return RandomHockeyClient(self.name, self.debug)

    def clientConnectionFailed(self, connector, reason):
        if self.debug:
            print("Connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        if self.debug:
            print("Connection lost - goodbye!")
        reactor.stop()


name = "Kek{}".format(random.randint(0, 999))

f = ClientFactory(name, debug=True)
reactor.connectTCP("localhost", 8023, f)
reactor.run()
