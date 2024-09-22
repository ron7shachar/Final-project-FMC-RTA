from SynchronizedAlgorithms.FMC_TA.FMC_TA_agents import FmcSP, FmcSR
from SynchronizedAlgorithms.SynchronizedSolver import SynchronizedSolverSOMAOP, VariableAssignment
import copy

dbug = True


class FMC_TA(SynchronizedSolverSOMAOP):
    def __init__(self, problem_id, providers, requesters, max_iteration=500, bid_type=0,
                 mailer=None, algorithm_version=0, min_work_split=0.01,
                 e=0.001):
        # version & bid
        self.repetitive = algorithm_version in [0, 2]
        self.updated_heuristic = algorithm_version in [0, 1]
        print("repetitive", self.repetitive)
        print("updated_heuristic", self.updated_heuristic)

        self.bid_type = bid_type
        self.max_iterations = max_iteration
        self.min_work_split = min_work_split
        self.e = e  # max allow delta price
        SPs = self.create_SPs(providers)
        SRs = self.create_SRs(requesters)
        SynchronizedSolverSOMAOP.__init__(self, problem_id=problem_id, providers=SPs, requesters=SRs,
                                          mailer=mailer, termination=max_iteration)

        # measures
        self.iteration = 0
        self.schedule = {}

    def execute_algorithm(self):
        print("--------------------execute_algorithm FMC------------")
        self.initialize()
        self.run_fmc()

    def initialize(self):
        for requester in self.all_requesters:
            requester.compute_initial_offers()

    def run_fmc(self):
        # self.iterate()
        iteration = 0
        while not self.isStable() and iteration < self.max_iterations:
            print('iteration :', iteration)
            self.iterate()
            iteration += 1
            # self.print_schedule()
            self.record_data()

    def iterate(self):

        # agents react to the messages they received in the last iteration and send new msgs
        self.requesters_react_to_msgs()
        # agents receive messages from current iteration
        self.agents_receive_msgs()

        self.providers_react_to_msgs()
        self.agents_receive_msgs()

        self.create_schedule()

    def requesters_react_to_msgs(self):
        for requester in self.all_requesters:
            requester.compute()
            requester.send_msgs()

    def providers_react_to_msgs(self):
        for provider in self.all_providers:
            provider.compute()
            provider.send_msgs()

    def agents_receive_msgs(self):
        self.number_of_messages_sent += len(self.mailer.msg_box)
        self.mailer.agents_receive_msgs()

    def create_SPs(self, simulation_providers_entities):
        SPs = [FmcSP(simulation_entity=provider, repetitive=self.repetitive, updated_heuristic=self.updated_heuristic)
               for provider in simulation_providers_entities]
        return SPs

    def create_SRs(self, simulation_requester_entities):
        SRs = [FmcSR(bid_type = self.bid_type,simulation_entity=requester, repetitive=self.repetitive,
                     min_work_split=self.min_work_split, e=self.e)
               for requester in simulation_requester_entities]
        return SRs

    def create_schedule(self):
        allocations = {}

        for provider in self.all_providers:
            for task in provider.get_schedule():
                if task.requester in allocations.keys():
                    if task.skill not in allocations[task.requester].keys():
                        allocations[task.requester][task.skill] = []
                else:
                    allocations[task.requester] = {}
                    allocations[task.requester][task.skill] = []
                allocations[task.requester][task.skill].append(task)

        for requester in allocations.keys():
            for skill in allocations[requester].keys():

                sub_allocations = allocations[requester][skill]
                part = sum([task.allocation for task in sub_allocations])
                # if part < 0.99999 or part > 1.000001:
                #     print(self.isStable())
                #     raise InvalidTimeSplitError(
                #         f'Invalid time split -> requester: {requester} , skill: {skill} , sum {part}')

                new_sub_allocations = {}
                for task in sub_allocations:
                    new_sub_allocations[task.arrival_time] = 0
                    new_sub_allocations[task.leaving_time] = 0
                in_work = []
                old_number = 0
                for time in sorted(new_sub_allocations.keys()):
                    for task in sub_allocations:
                        if task.arrival_time == time:
                            in_work.append(task)
                            new_sub_allocations[time] = old_number
                            old_number = len(in_work)

                    for task in in_work:
                        if task.leaving_time == time:
                            in_work.remove(task)
                            new_sub_allocations[time] = old_number
                            old_number = len(in_work)
                allocations[requester][skill] = new_sub_allocations
        self.schedule = allocations

    def isStable(self):
        if self.repetitive:
            print(f'lemgth   | SP | committed | free  | total |')
            print(f'______________________________________')
            for provider in self.all_providers:
                print('lemgth ', '| ', provider._id, ' |', " |    ", len(provider.committed_final_schedule), "    |  ",
                      len(provider.final_schedule), "  |  ",
                      len(provider.committed_final_schedule + provider.final_schedule), "  | ")

            for provider in self.all_providers:
                if not provider.isStable():
                    return False
        else:
            for requester in self.all_requesters:
                if not requester.stable:
                    return False

        return True

    def calculate_global_utility(self):  # fl חישוב יוטיליטי
        total_util = 0.0
        for requester_id in self.schedule.keys():
            requester = self.get_agent_by_id(requester_id)
            total_util += requester.simulation_entity.final_utility(simulation_times=self.schedule[requester_id])
        return total_util


class InvalidTimeSplitError(Exception):
    """Exception raised for errors in the input time split."""

    def __init__(self, message="Invalid time split"):
        self.message = message
        super().__init__(self.message)
