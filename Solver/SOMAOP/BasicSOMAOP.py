import copy
import math
from abc import ABC

from Simulator.CTTD.MedicalUnit import MedicalUnit
from Solver.SolverAbstract import Agent, Msg
from Simulator.SimulationComponents import ServiceProvider, ServiceRequester


## SOMAOP Messages ##

class SkillMessage(Msg):
    def __init__(self, sender_id, receiver_id, context):
        Msg.__init__(self, sender_id, receiver_id, context)

    def __str__(self):
        return "SkillMessage from " + str(self.sender_id) + " to " + str(self.receiver_id) + ": " + str \
            (self.context)


class DistanceMessage(Msg):
    def __init__(self, sender_id, receiver_id, context):
        Msg.__init__(self, sender_id, receiver_id, context)

    def __str__(self):
        return "DistanceMessage from " + str(self.sender_id) + " to " + str(self.receiver_id) + ": " + str \
            (self.context)

class BidMessage(Msg):
    def __init__(self, sender_id, receiver_id, context):
        Msg.__init__(self, sender_id, receiver_id, context)
    def __str__(self):
        return "Bid from " + str(self.sender) + " to " + str(self.receiver) + ": " + str \
            (self.information)


# RPA Offer Message
class OfferMessage(Msg):
    def __init__(self, sender_id, receiver_id, context):
        Msg.__init__(self, sender_id, receiver_id, context)

    def __str__(self):
        return "OfferMessage from " + str(self.sender) + " to " + str(self.receiver) + ": " + str \
            (self.information)

class ServiceProposalMsg(Msg):
    def __init__(self, sender_id, receiver_id, context):
        Msg.__init__(self, sender_id, receiver_id, context)

    def __str__(self):
        return "ServiceProposalMsg from " + str(self.sender) + " to " + str(self.receiver) + ": " + str \
            (self.information)

class GSResponseMsg(Msg):
    def __init__(self, sender_id, receiver_id, context):
        Msg.__init__(self, sender_id, receiver_id, context)

    def __str__(self):
        return "GSResponseMsg from " + str(self.sender) + " to " + str(self.receiver) + ": " + str \
            (self.information)

class GSUpdateServiceMessage(Msg):
    def __init__(self, sender_id, receiver_id, context):
        Msg.__init__(self, sender_id, receiver_id, context)

    def __str__(self):
        return "GSUpdateServiceMessage from " + str(self.sender) + " to " + str(self.receiver) + ": " + str \
            (self.information)

class UpdateServiceMessage(Msg):
    def __init__(self, sender_id, receiver_id, context):
        Msg.__init__(self, sender_id, receiver_id, context)

    def __str__(self):
        return "UpdateServiceMessage from " + str(self.sender) + " to " + str(self.receiver) + ": " + str \
            (self.information)
class SP(Agent, ABC):
    def __init__(self, simulation_entity: ServiceProvider, t_now, algorithm_version):
        Agent.__init__(self, simulation_entity=simulation_entity, t_now=t_now)
        # Provider Variables
        self.util_i = {}
        if isinstance(simulation_entity, MedicalUnit):
            self.skill_set = {key[0]: value for key, value in simulation_entity.workload.items()}
        else:
            self.skill_set = simulation_entity.skill_set

        # Algorithm Results
        self.neighbor_locations = {}  # {neighbor_id: location}
        self.schedule = []
        self.algorithm_version = algorithm_version
        self.neighbors_by_skill = {}  # {skill: [requester_ids]}

        # provider xi Variables
        self.xi_size = 0  # the amount of variables i have
        self.current_xi = {}  # variable assignments {x_id:assignment}
        self.domain = []  # [all domain options]
        self.reset_neighbors_by_skill()

    def __str__(self):
        return "SP " + Agent.__str__(self)

    def reset_util_i(self):
        self.util_i = {}

    def send_skills_msg(self, requester_id):
        msg_skills = Msg.MsgSkills(sender_id=self.id_, receiver_id=requester_id, context=self.skill_set)
        self.mailer.send_msg(msg_skills)  # todo communication

    def send_location_msg(self, agent_id):
        msg_location = Msg.MsgLocationAndSpeed(sender_id=self._id,
                                               context=[copy.deepcopy(self.simulation_entity.location),
                                                        self.simulation_entity.speed],
                                               receiver_id=agent_id)
        self.mailer.send_msg(msg_location)  # todo communication

    # 1 - calculate travel time by distance and speed
    def travel_time(self, start_location, end_location):
        return self.simulation_entity.travel_time(start_location, end_location)

    def reset_neighbors_by_skill(self):
        for skill in self.skill_set.keys():
            self.neighbors_by_skill[skill] = []
class SR(Agent, ABC):
    def __init__(self, simulation_entity: ServiceRequester, t_now, bid_type, algorithm_version):
        Agent.__init__(self, simulation_entity=simulation_entity, t_now=t_now)

        self.util_j = {}  # {skill:{provider:utility}}
        self.bid_type = bid_type  # int index for bid type within an algorithm
        self.skills_needed = copy.deepcopy(self.simulation_entity.skills_requirements)
        self.max_time = self.simulation_entity.max_time
        self.terminated = {}  # {skill:T\F}
        self.algorithm_version = algorithm_version


        # msg variables
        self.offers_received_by_skill = {}
        self.reset_offers_received_by_skill()

        # neighbor variables
        self.neighbors = []  # all neighbors ids
        self.neighbors_by_skill = {}  # {skill: [provider_ids]}
        self.reset_neighbors_by_skill()

        # Algorithm results
        self.neighbor_arrival_times = {}

        # utility variables
        self.simulation_times_for_utility = {}
        self.reset_simulation_times_for_utility()

    # 1 - calculates final utility according to team_simulation_times_for_utility dict
    def final_utility(self, SP_view=None):
        """
        method that get the relevant SPs and return the final utility - calc by simulation entity
        :param SP_view:
        :return:
        """
        raise NotImplementedError

    # reset methods
    # initiates neighbors_by_skill dict


    # initiates simulation_times_for_utility dict
    def reset_simulation_times_for_utility(self):
        for skill in self.skills_needed.keys():
            self.simulation_times_for_utility[skill] = {}

    # reset offers by skill
    def reset_offers_received_by_skill(self):
        self.offers_received_by_skill = {}
        for skill in self.skills_needed:
            self.offers_received_by_skill[skill] = []


    # utility methods
    def calculate_current_utility(self):
        self.simulation_entity.calculate_current_utility()

    def calculate_current_skill_cover(self):
        self.simulation_entity.calculate_current_skill_cover()

    def provider_require(self, provider):
        skills_in_common = [s for s in provider.skill_set if s in self.skills_needed]
        return provider.travel_time(start_location=provider.simulation_entity.location,
                                    end_location=self.simulation_entity.location) <= self.max_time \
               and len(skills_in_common) > 0

    def reset_neighbors_by_skill(self):
        for skill in self.skills_needed.keys():
            self.neighbors_by_skill[skill] = []