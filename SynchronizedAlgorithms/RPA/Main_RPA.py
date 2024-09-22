from SynchronizedAlgorithms.RPA.RPA_agents import RpaSP, RpaSR
from SynchronizedAlgorithms.SynchronizedSolver import SynchronizedSolverSOMAOP, VariableAssignment
import copy
dbug = True


class RPA(SynchronizedSolverSOMAOP):
    def __init__(self, problem_id, providers, requesters,  max_iteration, bid_type=0,
                 mailer=None, algorithm_version=0, alfa=0.7):

        # version & bid
        self.bid_type = bid_type
        self.version = algorithm_version # 0 - regular version 1 - SA version 2 -
        self.alfa = alfa

        SPs = self.create_SPs(providers)
        SRs = self.create_SRs(requesters)
        SynchronizedSolverSOMAOP.__init__(self, problem_id=problem_id, providers=SPs, requesters=SRs,
                                          mailer=mailer, termination=max_iteration)

        # measures
        self.globalUtility = 0
        self.total_util_over_iteration = {}
        self.iteration = 0
        self.percentCompleteOverIteration = {}
        self.number_of_messages_sent_iteration = {}
        self.number_of_messages_sent_total = 0


    def execute_algorithm(self):
        for iteration in range(-1, self.termination):
            if dbug:
                print("--------------------ITERATION " + str(iteration) +"------------")
            self.providers_react_to_msgs(iteration)
            self.agents_receive_msgs()

            # agents react to the messages they received in the last iteration and send new msgs
            self.requesters_react_to_msgs()
            # agents receive messages from current iteration
            self.agents_receive_msgs()

            self.record_data()
            if self.version == 5 and iteration == 0:
                break

    def providers_react_to_msgs(self, iteration):
        for provider in self.all_providers:
            if iteration == -1:
                provider.initialize()
            else:
                provider.compute()
            provider.send_msgs()

    def requesters_react_to_msgs(self):
        for requester in self.all_requesters:
            requester.compute()
            requester.send_msgs()



    def calculate_global_utility(self):
        total_util = 0
        SP_views = self.create_full_SP_views()
        for requester in SP_views:
            total_util += requester.get_utility_by_SP_view(SP_views[requester])
        return total_util

    def create_full_SP_views(self):
        all_SP_views = {}
        for requester in self.all_requesters:
            all_SP_views[requester] = []
            for provider_id in requester.neighbors:
                agent_object = self.get_agent_by_id(provider_id)
                if len(agent_object.current_xi) > 0:
                    all_SP_views[requester].append(agent_object.current_xi)

        return all_SP_views

    # create solver agents
    def create_SPs(self, simulation_providers_entities):
        SPs = [RpaSP(simulation_entity=provider, algo_version=self.version, alfa=self.alfa)
               for provider in simulation_providers_entities]
        return SPs

    def create_SRs(self, simulation_requester_entities):
        SRs = [RpaSR(simulation_entity=requester, bid_type=self.bid_type, algo_version=self.version)
               for requester in simulation_requester_entities]
        return SRs



