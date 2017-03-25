import random

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.protocols.basic import LineReceiver

from hockey.action import Action

import re
import numpy as np
from itertools import product, chain

class HockeyClient(LineReceiver, object):
    def __init__(self, name, debug):
        self.name = name
        self.debug = debug

        # state
        self.grid = np.zeros((15, 15))
        self.edge_taken = np.zeros((15, 15, 15, 15))
        self.blacklist = np.zeros((15, 15))

        self.ball_position = None
        self.goal = None
        self.goal_position = None
        self.powerup_position = None
        self.powerup = False

        # horizontal borders
        for i in range(14):
            self.mark_edge_as_taken((0, i), (0, i + 1))
            self.mark_edge_as_taken((14, i), (14, i + 1))

        # vertical borders
        for j in range(14):
            self.mark_edge_as_taken((j + 1, 0), (j, 0))
            self.mark_edge_as_taken((j + 1, 14), (j, 14))

    def connectionMade(self):
        self.sendLine(self.name)

    def sendLine(self, line):
        super(HockeyClient, self).sendLine(line.encode('UTF-8'))

    def lineReceived(self, line):
        line = line.decode('UTF-8')

        if self.debug:
            print('Server said:', line)
            print(self.grid)
            print(self.blacklist)

        match = re.match(r'ball is at \((\d+), (\d+)\) - (\d+)', line)
        if match:
            pos = int(match.group(1)), int(match.group(2))
            self.ball_position = pos
            self.grid[pos] = int(match.group(3))
            return

        match = re.match(r'your goal is (\w+) - \d+', line)
        if match:
            if match.group(1) == 'north':
                self.goal = 'south'
                self.goal_position = (15, 7) # go south
            else:
                self.goal = 'north'
                self.goal_position = (-1, 7) # go north
            self.init_blacklist()
            return

        match = re.match(r'power up is at \((\d+), (\d+)\) - \d+', line)
        if match:
            x, y = int(match.group(1)), int(match.group(2))
            self.powerup_position = y, x
            self.init_blacklist()
            return

        if re.match(r'polarity of the goal has been inverted - \d+', line):
            self.goal = 'south' if self.goal == 'north' else 'north'
            self.goal_position = 14 - self.goal_position[0], self.goal_position[1]
            self.init_blacklist()
            return

        match = re.match(r'(.*) did go (?:power )?(.*) - (\d+)', line)
        if match:
            dx, dy = Action.move[(match.group(2))]
            new_ball_position = self.ball_position[0] + dy, self.ball_position[1] + dx
            self.grid[new_ball_position] = int(match.group(3))
            self.mark_edge_as_taken(self.ball_position, new_ball_position)
            self.ball_position = new_ball_position
            if new_ball_position == self.powerup_position:
                self.powerup_position = None
                self.init_blacklist()
                if self.name == match.group(1):
                    self.powerup = True
            return

        if re.match(r'.* won a goal was made - \d+', line):
            return # fin de la partie

        if '{} is active player'.format(self.name) in line or 'invalid move' in line:
            self.sendLine(self.play_game())

def manhattan(a, b, c=None):
    if c:
        return min(abs(b[0] - a[0]) + abs(b[1] - a[1]), abs(c[0] - a[0]) + abs(c[1] - a[1]))
    else:
        return abs(b[0] - a[0]) + abs(b[1] - a[1])

class RandomHockeyClient(HockeyClient):
    def neighborhood(self, position):
        for edge, delta in Action.move.items():
            dx, dy = delta
            pos = position[0] + dy, position[1] + dx
            if 0 <= pos[0] <= 14 and 0 <= pos[1] <= 14:
                if not self.edge_taken[position][pos]:
                    yield edge, pos

    def init_blacklist(self):
        self.blacklist = np.zeros((15, 15))

        # center
        self.blacklist[7, 7] = True

        # corners
        self.blacklist[0, 0] = True
        self.blacklist[0, 14] = True
        self.blacklist[14, 0] = True
        self.blacklist[14, 14] = True

        if self.goal == 'north':
            # protect south goal
            self.blacklist[14, 7] = True
            self.blacklist[13, 5] = True
            self.blacklist[13, 6] = True
            self.blacklist[13, 7] = True
            self.blacklist[13, 8] = True
            self.blacklist[13, 9] = True
        else:
            self.blacklist[0, 7] = True
            self.blacklist[1, 5] = True
            self.blacklist[1, 6] = True
            self.blacklist[1, 7] = True
            self.blacklist[1, 8] = True
            self.blacklist[1, 9] = True

        # powerup surroundings
        if self.powerup_position:
            for pos_edge, pos in self.neighborhood(self.powerup_position):
                if self.grid[pos] == 0:
                    self.blacklist[pos] = True

    def update_blacklist(self):
        for y in range(1, 14):
            if len(list(self.neighborhood((y, 0)))) == 1:
                self.blacklist[(y, 0)] = True
            if len(list(self.neighborhood((y, 14)))) == 1:
                self.blacklist[(y, 14)] = True
        for x in chain(range(1, 5), range(9, 14)):
            if len(list(self.neighborhood((0, x)))) == 1:
                self.blacklist[(0, x)] = True
            if len(list(self.neighborhood((14, x)))) == 1:
                self.blacklist[(14, x)] = True

        for pos in zip(*np.nonzero(self.blacklist)):
            for accessible in [u for u_edge, u in self.neighborhood(pos) if not self.blacklist[u]]:
                self.spooke(accessible, pos)

    def mark_edge_as_taken(self, a, b):
        self.edge_taken[a][b] = True
        self.edge_taken[b][a] = True

    def spooke(self, u, v):
        a = [w for edge_w, w in self.neighborhood(u) if v != w and not self.blacklist[w]]

        if len(a) == 0:
            self.blacklist[u] = True
        elif len(a) == 1:
            self.blacklist[u] = True
            self.spooke(a[0], u)
        else:
            pass # there is a way out!

    def play_game(self):
        self.update_blacklist()

        # Use the powerup if near the goal
        if self.powerup and self.ball_position[0] == 2 and self.goal == 'north':
            # if self.ball_position[1] == 4:
                # return 'power north east'
            if self.ball_position[1] == 5:
                return 'power north east'
            if self.ball_position[1] == 6:
                return 'power north'
            if self.ball_position[1] == 7:
                return 'power north'
            if self.ball_position[1] == 8:
                return 'power north'
            if self.ball_position[1] == 9:
                return 'power north west'
            # if self.ball_position[1] == 10:
                # return 'power '

        if self.powerup and self.ball_position[0] == 13 and self.goal == 'south':
            # if self.ball_position[1] == 4:
                # return 'power south east'
            if self.ball_position[1] == 5:
                return 'power south east'
            if self.ball_position[1] == 6:
                return 'power south'
            if self.ball_position[1] == 7:
                return 'power south'
            if self.ball_position[1] == 8:
                return 'power south'
            if self.ball_position[1] == 9:
                return 'power south west'
            # if self.ball_position[1] == 10:
                # return 'power south west'

        if self.ball_position[0] == 0 and self.goal == 'north':
            if self.ball_position[1] == 6:
                return 'north east'
            if self.ball_position[1] == 7:
                return 'north'
            if self.ball_position[1] == 8:
                return 'north west'

        if self.ball_position[0] == 14 and self.goal == 'south':
            if self.ball_position[1] == 6:
                return 'south east'
            if self.ball_position[1] == 7:
                return 'south'
            if self.ball_position[1] == 8:
                return 'south west'

        # rebound in goal
        if self.ball_position[0] == 1 and self.goal == 'north':
            if self.ball_position[1] == 5:
                return 'north east'
            if self.ball_position[1] == 6:
                return 'north'

            if self.ball_position[1] == 7:
                return 'north west'  # or north east, same thing

            if self.ball_position[1] == 8:
                return 'north'
            if self.ball_position[1] == 9:
                return 'north west'

        # rebound in goal
        if self.ball_position[0] == 13 and self.goal == 'south':
            if self.ball_position[1] == 5:
                return 'south east'
            if self.ball_position[1] == 6:
                return 'south'

            if self.ball_position[1] == 7:
                return 'south west'  # or south east, same thing

            if self.ball_position[1] == 8:
                return 'south'
            if self.ball_position[1] == 9:
                return 'south west'

        valid_choices = [neighbor for neighbor in self.neighborhood(self.ball_position)]
        better_choices = [neighbor for neighbor in valid_choices if not self.blacklist[neighbor[1]]]

        if better_choices:
            return min(better_choices, key=lambda n: manhattan(n[1], self.goal_position, self.powerup_position))[0]
        else:
            valid_choice = min(valid_choices, key=lambda n: manhattan(n[1], self.goal_position, self.powerup_position))
            valid_choice_neighbors = len([u for u_edge, u in self.neighborhood(valid_choice[1]) if not self.blacklist[u]])

            if valid_choice_neighbors > 0:
                self.powerup = False
                return "power {}".format(valid_choice[0])
            else:
                return valid_choice[0]

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
