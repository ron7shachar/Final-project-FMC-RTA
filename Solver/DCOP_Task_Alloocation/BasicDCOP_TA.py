import copy
import math
from Solver.SolverAbstract import Agent, Msg, Mailer


class DCOP_TA_Agent():
    def __init__(self, id_, problem_id, skill_set, travel_speed):
        # problem variables
        self.problem_id = problem_id
        self.mailer = None

        # agent variables
        self.id_ = id_
        self.skill_set = skill_set
        self.travel_speed = travel_speed
        self.current_location = []

        self.task_neighbors = set()
        self.task_skill_map = None  # {task:{skill:amt}}
        self.agent_neighbors = set()

        # DCOP variables
        self.xi_size = 0
        self.current_xi = {}  # {x_id:assignment}
        self.domain = []  # all options for task, skill assignment [Variable_Assignments] (same for all x_i)
        self.agent_view = {}  # {a_id: current_assigned_x of neighbor agent}

        # Measures
        self.NCLO = 0

    def __eq__(self, other):
        return self.id_ == other.id_

    def __hash__(self):
        return self.id_

    def __str__(self):
        return "Agent ID: " + str(self.id_)

    # get to know my mailer
    def meet_mailer(self, mailer_input):
        self.mailer = mailer_input

    # initialize algorithm, the algorithms first iteration
    def initialize(self):
        raise NotImplementedError()

    # compute after receiving information from last iteration
    def compute(self):
        raise NotImplementedError()

    # after computation broadcast the new information
    def send_msgs(self):
        raise NotImplementedError()

    # receive a msg and update local context
    def agent_receive_a_single_msg(self, msg):
        raise NotImplementedError()

    def travel_time(self, start_location, end_location):
        distance = round(math.sqrt(sum((px - qx) ** 2.0 for px, qx in zip(start_location, end_location))), 2)
        distance_in_time = distance / self.travel_speed
        return distance_in_time

    def create_task_skill_map(self):  # {task:{skill:amt}}
        self.task_skill_map = {}
        for task in self.task_neighbors:
            self.task_skill_map[task] = {}

            for skill, amount in task.skills_needed.items():
                if skill in self.skill_set.keys():
                    amt = min(amount, self.skill_set[skill])
                    self.task_skill_map[task][skill] = amt

            if not self.task_skill_map[task]:
                del self.task_skill_map[task]

    def calculate_xi_size(self):
        for task in self.task_skill_map:
            self.xi_size += len(self.task_skill_map[task])

    def create_domain(self):  # domain for each variable = all options for task, skill [Variable_Assignments]
        task_and_skill_tuples = self.create_all_task_and_skill_tuples()  # [(task,skill)]
        for task_and_skill in task_and_skill_tuples:
            task = task_and_skill[0]
            skill = task_and_skill[1]
            location = task.location
            self.domain.append(DCOP_TA_Agent_Variable_Assignment(task.id_, skill, location))

    def create_times_for_assignment(self):
        start_time = 0
        start_location = self.current_location
        skills_temp = copy.deepcopy(self.skill_set)

        for xi, assignment in self.current_xi.items():
            task = self.get_task_by_id(assignment.task)
            skill = assignment.skill

            skill_amount = min(skills_temp[skill], task.skills_needed[skill])

            assignment.amount = skill_amount
            skills_temp[assignment.skill] -= skill_amount

            assignment.duration = task.time_per_skill_unit[assignment.skill] * skill_amount

            arrival_time = round(start_time + self.travel_time(start_location, assignment.location), 2)
            leaving_time = round(arrival_time + assignment.duration, 2)
            assignment.arrival_time = arrival_time
            assignment.leaving_time = leaving_time

            start_time = leaving_time
            start_location = assignment.location

    def get_task_by_id(self, id_):
        for task in self.task_neighbors:
            if id_ == task.id_:
                return task

    def create_all_task_and_skill_tuples(self):  # [(task,skill)]
        task_and_skill_tuples = []
        for task in self.task_skill_map.keys():
            for skill in self.task_skill_map[task].keys():
                task_and_skill_tuples.append((task, skill))

        return task_and_skill_tuples
