import copy
import math

from Simulator.CTTD.MedicalUnit import MedicalUnit
from Solver.SOMAOP.BasicSOMAOP import SP, SR

dbug = True


class VariableAssignment:
    def __init__(self, provider=None, requester=None, skill=None, location=None, amount=None, duration=0.0, arrival_time=None, leaving_time=None,
                 utility=None, mission=None, max_capacity=None, original_object=None, accept=False, last_workload_use=0.0,travel_time=0.0):
        if original_object is not None: #todo remove
            self.copy_constructor(original_object)
            return

        self.provider = provider
        self.requester = requester
        self.skill = skill
        self.location = location
        self.amount = amount
        self.duration = duration
        self.arrival_time = arrival_time
        self.leaving_time = leaving_time
        self.utility = utility
        self.max_capacity = max_capacity
        self.accept = accept  # has offers accept - for incremental version
        self.last_workload_use = last_workload_use # the last time that the workload has been done
        self.travel_time = travel_time
        if mission is None:
            self.mission = []
        else:
            self.mission = mission


    def copy_constructor(self, original):
        self.provider = original.provider
        self.requester = original.requester
        self.skill = original.skill
        self.location = original.location
        self.amount = original.amount
        self.duration = original.duration
        self.arrival_time = original.arrival_time
        self.leaving_time = original.leaving_time
        self.utility = original.utility
        self.mission = copy.deepcopy(original.mission)
        self.max_capacity = copy.deepcopy(original.max_capacity)
        self.accept = original.accept
        self.last_workload_use = original.last_workload_use
        self.location = copy.deepcopy(original.location)
        self.travel_time = copy.deepcopy(original.travel_time)


    def accept_offer(self):
        self.accept = True

    def __str__(self):
        mission_list = " "
        for mis in self.mission:
            if isinstance(mis, dict):
                mission_list += "\n " + str(mis['mission'])
        return "SP " + str(self.provider) + " SR " + str(self.requester) + " skill " + str(self.skill) + \
               " arrival: " + str(self.arrival_time) + " leaving: " + str(self.leaving_time) \
               + " amount: " + str(self.amount) + " utility: " + str(self.utility) + " " + mission_list

    # for comparing with ==
    def __eq__(self, other):
        return self.provider == other.provider and self.requester == other.requester \
               and self.skill == other.skill and self.arrival_time == other.arrival_time


    # for inserting in hashable objects like list
    def __hash__(self):
        return self.requester

    # for copy.deepcopy()
    def __deepcopy__(self, memodict={}):

        copy_object = VariableAssignment(provider=self.provider, requester=self.requester, skill=self.skill,
                                         location=self.location, amount=self.amount, duration=self.duration,
                                         arrival_time=self.arrival_time, leaving_time=self.leaving_time,
                                         utility=self.utility,mission=copy.deepcopy(self.mission),
                                         max_capacity=copy.deepcopy(self.max_capacity), accept=self.accept, last_workload_use=self.last_workload_use, travel_time=copy.deepcopy(self.travel_time))
        return copy_object


class SynchronizedSolverSOMAOP(object):
    def __init__(self, problem_id, providers: [SP], requesters: [SR], mailer, termination):
        # solver variables
        self.problem_id = problem_id
        self.all_providers = providers
        self.all_requesters = requesters
        self.mailer = mailer  # the mailer - deliver message only
        self.termination = termination
        self.agents = providers + requesters
        self.number_of_messages_sent = 0

        # NCLO variables
        self.NCLO = 0
        self.total_util_over_NCLO = {}

        # initialized
        self.assign_neighbors()


    # 3 - creates neighboring agents by threshold distance - symmetrical
    def assign_neighbors(self):
        for provider in self.all_providers:
            for requester in self.all_requesters:
                if requester.provider_require(provider=provider):
                    skills_in_common = [s for s in provider.skill_set if s in requester.skills_needed]
                    provider.neighbors.append(requester.getId())
                    requester.neighbors.append(provider.getId())
                    provider_skills_available_in_common = {}
                    requester_skills_needs_in_common = {}
                    for skill in skills_in_common:
                        requester.neighbors_by_skill[skill].append(provider.getId())
                        provider_skills_available_in_common[skill] = provider.skill_set[skill]
                        requester_skills_needs_in_common[skill] = requester.skills_needed[skill]
                        provider.neighbors_by_skill[skill].append(requester.getId())
                        provider.xi_size += 1
                        domain_opt = VariableAssignment(provider.getId(), requester.getId(), skill,
                                                        copy.deepcopy(requester.location))
                        if isinstance(provider.simulation_entity, MedicalUnit):
                            domain_opt.max_capacity = copy.deepcopy(provider.simulation_entity.get_max_capacity())

                        provider.domain.append(domain_opt)
                    provider.neighbor_locations[requester.getId()] = copy.deepcopy(requester.location)

    def meat_mailer(self, mailer):
        self.mailer = mailer

    # initialize the agents if necessary and start run algorithm
    def execute(self):
        for agent in self.all_providers + self.all_requesters:
            agent.initielized(self)
        self.execute_algorithm()

    def execute_algorithm(self):
        raise NotImplementedError()

    # finds agent by id (from providers and requesters)
    def get_agent_by_id(self, agent_id):
        for agent in self.all_providers + self.all_requesters:
            if agent.getId() == agent_id:
                return agent
        else:
            return None

    def reset_agent_NCLOS(self):
        for agent in self.all_providers+self.all_requesters:
            agent.NCLO = 0

    def find_max_NCLO(self):
        max_NCLO = 0
        for agent in self.all_providers+self.all_requesters:
            if agent.NCLO > max_NCLO:
                max_NCLO = agent.NCLO
        return max_NCLO

    def agents_receive_msgs(self):
        self.number_of_messages_sent += len(self.mailer.msg_box)
        self.mailer.agents_receive_msgs()

    def update_current_NCLO(self):
        self.NCLO += self.find_max_NCLO()

    def record_data(self):
        util = self.calculate_global_utility()
        self.update_current_NCLO()
        self.reset_agent_NCLOS()
        self.total_util_over_NCLO[self.NCLO] = util
        if dbug: print('NCLO: %s, Utility: %s'% (self.NCLO, util))

    def calculate_global_utility(self):
        raise NotImplementedError()
