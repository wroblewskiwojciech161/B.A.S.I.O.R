from threading import Thread
import time
import json
from .dataloader import DataLoader
from .tram import Tram
from .comunicate_manager import ComuinicateManager
from .city_graph import CityGraph
from .substituteroute import SubstituteRoute


class LogicConnector(Thread):
    def __init__(self):
        super(LogicConnector, self).__init__()
        self.State = False
        self.can_fix = True
        self.trams = []
        self.next_move = None
        self.Loader = DataLoader()
        self.city_graph = CityGraph(self.Loader.graph)

        self.load_data()

    # Load all trams specified in "data/lines_to_load.csv" and their routes (regular ones and reversed)
    def load_data(self):
        all_trams_data = self.Loader.load_all_lines()

        for i in range(0, len(all_trams_data), 2):
            self.trams.append(
                Tram(str(all_trams_data[i][0]), str(all_trams_data[i][1]), str(all_trams_data[i + 1][1]),
                     self.Loader))
            self.trams.append(
                Tram(str(all_trams_data[i + 1][0]), str(all_trams_data[i + 1][1]), str(all_trams_data[i][1]),
                     self.Loader, is_reversed=True))

    # Used by ClientHandler to deliver message form Client
    def push(self, message):
        message = json.loads(json.dumps(message))
        if message["type"] == 'destroy':  # If message "destroy" is obtained from client
            self.damage_route(message["coordinates"])  # check how client actions affect tram routes
            if self.next_move is None:
                self.next_move = ComuinicateManager.send_path(self.trams, "2")
                self.State = not self.State

    # Used by ClientHandler to determine if there is any change in game, which is supposed to be send to Client
    def get_state(self):
        return self.State

    # Used by ClientHandler to get changelog of simulation state in order to deliver it to Client
    def get_changes(self):
        temp = self.next_move.copy()
        self.next_move = None

        self.State = False if self.State is True else False

        return json.dumps(temp)

    # Method that sends tram coordinates every x seconds to client
    def run(self):
        while True:

            if self.next_move is None:
                self.next_move = ComuinicateManager.send_trams_coords(self.trams)
                self.State = not self.State
            if self.can_fix:
                self.can_fix_routes()
            time.sleep(0.3)

    # Method to check how deleting edges influences tram routes and takes care of it
    def damage_route(self, coords):
        self.can_fix = False
        self.city_graph.remove_edge(coords, 350)

        for tram in self.trams:
            temp_route = SubstituteRoute.calculate_bypass(self.city_graph.graph, tram.current_route)
            tram.apply_bypass(temp_route)

        self.can_fix = True

    # Method that checks if any of edges can be fixed if so then trams which were halted check if they are clear to go
    # If any tram had applied bypass, then it won't change its route to default until it gets to loop
    def can_fix_routes(self):
        was_fixed = self.city_graph.check_penalties()

        if was_fixed:
            for tram in self.trams:
                if tram.is_halted:
                    temp_route = SubstituteRoute.calculate_bypass(self.city_graph.graph, tram.current_route)
                    tram.apply_bypass(temp_route)