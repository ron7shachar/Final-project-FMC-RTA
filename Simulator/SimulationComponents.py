import abc
import enum
import random
import math
from abc import ABC
import copy


# represents all the simulation base abstract components

_width = None
_length = None


# abstract simulation creator
class Simulation:
    def __init__(self, number_of_providers, number_of_requesters, prob_id):
        self.number_of_requesters = number_of_requesters
        self.number_of_providers = number_of_providers
        self.problem_id = prob_id
        self.random_num = random.Random(prob_id)
        self.requesters = []
        self.providers = []

    # creates locations for agents in a list according to the thresholds given in params
    def create_initial_locations(self, agents, location_params):
        min_x = location_params["location_min_x"]
        max_x = location_params["location_max_x"]
        min_y = location_params["location_min_y"]
        max_y = location_params["location_max_y"]

        for a in agents:
            rand_x = round(self.random_num.uniform(min_x, max_x), 2)
            rand_y = round(self.random_num.uniform(min_y, max_y), 2)
            a.location = [rand_x, rand_y]

    def get_agent(self, agent_id):
        for agent in self.providers + self.requesters:
            if agent.id_ == agent_id:
                return agent


# basic entity has id , update time and location
class Entity:
    """
        Class that represents a basic entity in the simulation
    """

    def __init__(self, _id, last_time_updated=0, location=[0.0, 0.0]):
        """
        :param _id: the entity id
        :param last_time_updated: the last time that the entity updated (initial is time born)
        :param location:  the entity current location type: list of coordination
        """

        self._id = _id
        self.last_time_updated = last_time_updated
        self.location = location

    def update_location(self, location):
        """
        :param location: the next entity location
        :return: None
        """
        self.location = location

    def update_last_time(self, tnow):
        """
        :param tnow: next time update
        :return: None
        """
        self.last_time_updated = tnow if tnow > self.last_time_updated else Exception\
            ("times bug! last time in higher then tnow!")

    def distance_from_other_entity(self, other):
        """
        :param other: other entity
        :return: distance between self and other entity
        :rtype: float
        """
        return calc_distance(self.location, other.location)

    def getId(self):
        return self._id

    def __str__(self):
        return 'id: ' + self._id + ' location: '.join(self.location) + ' last time update: ' + self.last_time_updated

    def __hash__(self):
        return hash(self._id)

    def __eq__(self, other):
        return self._id == other._id

    @staticmethod # todo - copied from Agent to here because of loop import issues
    def number_of_comparisons(amount_chosen=0, amount_available=0):
        """
        calc the NCLO
        :param amount_chosen:
        :param amount_available:
        :return: NCLO
        """
        NCLO = 0

        for i in range(1, amount_chosen + 1):
            if amount_available <= 0:
                break

            NCLO += amount_available - 1
            amount_available -= 1

        return NCLO


# status for sp
class Status(enum.Enum):
    """
    Enum that represents the status of the player in the simulation
    """
    IDLE = 0
    ON_MISSION = 1
    TO_MISSION = 2


# basic sp: status, location, schedule, travel speed, skill and workload
class ServiceProvider(Entity, ABC):
    """
    A class that represent a service provider
    """

    def __init__(self, _id, time_born,  speed, skills, status=Status.IDLE,
                 base_location=None, productivity=1, location=[0.0, 0.0]):
        """
        :param _id: the entity id
        :rtype int
        :param time_born: the entity born time (update as last time)
        :rtype float
        :param location: the current location of the entity - generated from map class
        :rtype [float]
        :param speed: the service provider speed
        :rtype float
        :param skills: list of providable skills_activities
        :rtype (skill)
        :param status: the service provider status in the simulation
        :rtype Status
        :param base_location: The service provider base location case has one
        :rtype [float]
        :param productivity: entity productivity between 0 and 1
        :rtype float
        """
        Entity.__init__(self, _id=_id, last_time_updated=time_born, location=location)
        self.productivity = productivity
        self.base_location = base_location
        self.status = status
        self.skills = skills
        self.speed = speed
        self.workload = dict.fromkeys(skills, 0)  # initiate the workload of each skill to 0
        self.scheduled_services = [Service]
        # the services that were scheduled list of Service object

    def update_workload_each_skill(self, skill, capacity):
        """
        :param skill: The skill
        :param capacity: The workload of the skill
        :rtype float
        :return: None
        """
        self.workload[skill] = capacity if skill in self.workload.keys() else False

    def init_skill_workload(self, skills_set):
        """
        init all workload at ones
        :param skills_set: {skill: units}
        :return: None
        """
        self.workload = skills_set

    def provide_service(self, skill, workload):
        """
        reduce the workload of a skill
        :param skill: the providable skill
        :param workload: the workload should be reduced from current capacity
        :return: boolean if the workload is above the capacity
        """
        self.workload[skill] -= workload if skill in self.workload.keys() and self.workload[skill] >= workload\
            else False

    def __str__(self):
        return " Service Provider id: " + self._id + " last update time: " + self.last_time_updated + \
               " current location: " + self.location + " free workload: " + self.workload

    def __eq__(self, other):
        self._id == other._id

    def get_free_workload(self, skill):
        """
        return the free workload for allocation by skill
        :return: float
        """
        return self.workload[skill]

    def reset_workload(self, skill, workload):
        self.workload[skill] = workload

    def travel_time(self, start_location, end_location):
        distance = calc_distance(start_location, end_location)
        distance_in_time = round(distance / self.speed, 2)
        return distance_in_time

    @abc.abstractmethod
    def accept_offers(self, offers_received, allocation_version=0):
        """
        allocate the offers by the ordered received
        :return: NCLO, current_xi, response_offers
        """
        raise NotImplemented

    @abc.abstractmethod
    def accept_incremental_offer(self, offers_received, current_xi):
        """
        allocate the offers by the ordered received
        :return: NCLO, current_xi, response_offers
        """
        raise NotImplemented

    def accept_full_schedule_offer(self, offers_received):
        """
        allocate the offers by the ordered received
        :return: NCLO, current_xi, response_offers
        """
        raise NotImplemented


# basic sr: location, time_max, skills_activities requirement, skills_activities definition
class ServiceRequester(Entity, ABC):
    """
        A class that represent a service provider
    """

    def __init__(self, _id, time_born,  skills, max_time=math.inf, location=[0.0, 0.0]):
        """
        :param _id: the entity id
        :rtype int
        :param time_born: the entity born time (update as last time)
        :rtype float
        :param location: the current location of the entity - generated from map class
        :rtype [float]
        :param skills: list of require skills_activities
        :rtype [skill]
        :param max_time: the maximum time fo each skill need to complete (infinity if not initiate)
        :rtype float

        """
        Entity.__init__(self, _id=_id, last_time_updated=time_born, location=location)
        self.max_time = max_time
        self.skills = skills  # list of skills_activities
        self.skills_requirements = dict.fromkeys(skills, 0)
        self.skill_weights = dict.fromkeys(skills, 0.33)

        # initiate the requirements of each skill. dict-> Skill: workload=0

        self.max_required = dict.fromkeys(skills, 1)  # {skill: max_required} max cap for each skill
        self.max_util = dict.fromkeys(skills, max_time)  # {skill: max_time} max_utile for each skill
        self.finished = False  # when all the skill requirements completed true
        self.cap = 1  # the benefit from working simultaneously on few services
        self.scheduled_services = [Service]
        # the services that were scheduled list of Service object
        self.simulation_times_for_utility = {}  # times for utility calculation

    def init_skill_definition(self, skills_needed=None, max_required=None, max_util=None):
        if skills_needed is not None:
            self.skills_requirements = skills_needed
        if max_required is not None:
            self.max_required = max_required
        if max_util is not None:
            self.max_util = max_util

    def reduce_skill_requirement(self, skill, workload):
        """
        Reduce the workload from a service by a skill
        :param skill: the reduced service id
        :type Skill
        :param workload: the workload to reduce
        :return: None if success else exception
        """
        self.skills_requirements[skill] -= workload if self.skills_requirements[skill] > workload else \
            Exception("The workload is higher than the requirements")

    def add_scheduled_service(self, service):
        """
        add a service to schedule services
        :param service: the service provide
        """
        self.scheduled_services.append(service)

    def initiate_scheduled_services(self):
        """
        initiate all the scheduled services
        """
        self.scheduled_services.clear()

    def calc_utility_by_schedule(self, skills=None, skill_iteration_schedule_plans=None):
        if skills is None: skills = self.skills_requirements
        """
        calc the utility from scheduled services - this is used in extend class
        :return: the utility from scheduled services
        """
        raise NotImplementedError()

    def calculate_current_utility(self):
        """
        :return: utility by schedule
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def calc_converge_bid_to_offer(self, skill, offer):
        """
        :param skill:
        :return: utility for an offer by bid type
        """
        raise NotImplementedError()

    def calculate_current_skill_cover(self):
        """
        this method return the percent of skills_activities that plant
        :return:
        """
        raise NotImplementedError

    def allocate_requirements_by_providable_skills_time_workload(self, skill, workload, start_time):
        """
        get a providable skills_activities, start time and workload and scheduled them
        :return: update the self schedule raise exception - this is used in extend class
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def allocated_offers(self, skills_needed_temp, offers_received_by_skill, allocation_version=0):
        """
        methods that allocated the SPs offers
        :return: list of allocated offers to be sent back to the SPs
        """

    def create_schedules_by_skill_by_SP_view(self, SP_view):
        """
        :param SP_view: [{sp:[variable_assignment]}]
        :return: {skill:[variable_assignment]}
        """
        schedules_by_skill = {}
        for xi in SP_view:
            for value in xi.values():
                if value.requester == self._id:
                    if value.skill not in schedules_by_skill:
                        schedules_by_skill[value.skill] = []
                    schedules_by_skill[value.skill].append(value)
        return schedules_by_skill

    def __str__(self):
        return " Service Require id: " + self._id + " last update time: " + self.last_time_updated +\
                " current utility: " + self.calc_utility_by_schedule()

    def __eq__(self, other):
        return self._id == other._id

    def reset_simulation_times_for_utility(self, skills):
        for skill in skills.keys():
            self.simulation_times_for_utility[skill] = {}


# service: composed of a skill and the workload  and start time to be provided in an SR
class Service:
    """
    a class that represent a service: composed of a skill and the workload to be provided in an SR

    """
    def __init__(self, _id, sr, skill, start_time, workload=1):
        """
        :param _id: the service id = service_requester_id + order id
        :rtype int
        :param sr: the service provider id
        :rtype: int
        :param skill: skills_activities needed to complete the service
        :rtype Skill
        :param start_time: the time to start the service
        :rtype float
        :param workload: the amount of workload to be provided
        :rtype float

        """

        self.workload = workload
        self.start_time = start_time
        self.skill = skill
        self._id = _id
        self.sr = sr
        self.duration = self.calc_duration()
        self.utility = self.calc_utility()
        self.finished = False  # if the service completed

    def calc_utility(self):
        """
        :return: the utility from working on the service by start time, workload, number of service
        providers
        """
        return self.skill.calc_utility(self.workload, self.start_time)


# the map for the problem
class MapSimple:
    """
    The class represents a map for the simulation. The entities must be located by the def generate_location.
    One map for each simulation.
    """

    def __init__(self, length, width, seed):
        """
        :param length: The length of the map
        :param width: The length of the map
        :param seed: seed for random object
        """
        self.length = length
        self.width = width
        global _length
        _length = length
        global _width
        _width = width
        self.rand = random.Random(seed)

    def generate_location(self):
        """
        :return: random location on map
        :type: list of floats
        """
        x1 = self.rand.random()
        x2 = self.rand.random()
        return [self.width*x1, self.length*x2]

    def get_the_center_of_the_map_location(self):
        return [self.width / 2, self.length / 2]


# represent a skill
class Skill:
    """
    Class that represent all the skills_activities that entity can have or require
    """
    def __init__(self, skill_name=None, skill_id=0):
        """

        :param skill_name:  The skill type name (if dkill name is none, name = skill id as str)
        :rtype str
        :param skill_id: the skill id
        :rtype int
        """
        self.skill_id = skill_id
        if skill_name is None:
            self.skill_name = str(self.skill_id)
        else:
            self.skill_name = skill_name

    def __eq__(self, other):
        return self.skill_id == other.skill_id

    def __str__(self):
        return self.skill_name


def calc_distance(location1, location2):
    """
    :param location1: entity 1 location list of coordination
    :param location2: entity 1 location list of coordination
    :return: Euclidean distance
    :rtype float
    """
    return math.dist(location1, location2)


def calc_distance_between_two_entities(entity1: Entity, entity2: Entity):
    return calc_distance(entity1.location, entity2.location)


def get_skill_amount_dict(offers):
    skill_amount_dict = {}
    for offer in offers:
        skill_amount_dict[offer] = [offer.amount]
        offer.amount = 0
        offer.leaving_time = offer.arrival_time
    return skill_amount_dict