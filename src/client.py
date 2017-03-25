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
        self.grid = np.zeros(shape=(11, 11))
        self.edge_taken = np.zeros(shape=(11, 11, 11, 11))
        self.ball_position = (5, 5)
        self.goal = False

        self.grid[5, 5] = True

    def connectionMade(self):
        self.sendLine(self.name)

    def sendLine(self, line):
        super(HockeyClient, self).sendLine(line.encode('UTF-8'))

    def lineReceived(self, line):
        line = line.decode('UTF-8')

        if self.debug:
            print('Server said:', line)
            print(self.grid)

        match = re.match(r'ball is at \((\d+), (\d+\)) - \d+', line)
        if match:
            self.ball_position = int(match.group(1)), int(match.group(2))
            return

        match = re.match(r'your goal is (\w+) - \d+', line)
        if match:
            self.goal = match.group(1)
            return

        match = re.match(r'\w+ did go (\w+) - \d+', line)
        if match:
            direction = match.group(1)
            return

        if re.match(r'\w+ won a goal was made - \d+', line):
            return # fin de la partie

        if '{} is active player'.format(self.name) in line or 'invalid move' in line:
            self.sendLine(self.play_game())

    def play_game():
        return Action.from_number(random.randint(0, 7))

class ClientFactory(protocol.ClientFactory):
    def __init__(self, name, debug):
        self.name = name
        self.debug = debug

    def buildProtocol(self, addr):
        return HockeyClient(self.name, self.debug)

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
