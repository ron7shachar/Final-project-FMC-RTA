import abc
import copy
import threading
from abc import ABC
import random

from Simulator.SimulationComponents import Entity

message_debug = False


# message passing and communication objects
class Msg(object):

    def __init__(self, sender, receiver, information, is_with_perfect_communication=None):
        """

        :param sender: sender id
        :rtype int
        :param receiver: receiver id
        :rtype int
        :param information: is the context
        :param is_with_perfect_communication:
        """
        self.sender = sender

        self.receiver = receiver

        self.information = information

        self.msg_time = None  # in NCLO

        self.timestamp = None

        self.is_with_perfect_communication =is_with_perfect_communication

    def set_time_of_msg(self, delay):
        """
        how long the message is delay
        :param delay:
        :return: float
        """
        self.msg_time = self.msg_time + delay

    def add_current_NCLO(self, NCLO):
        self.msg_time = NCLO

    def add_timestamp(self, timestamp):
        self.timestamp = timestamp


class ClockObject:
    def __init__(self):
        self.clock = 0.0
        self.lock = threading.RLock()
        self.idle_time = 0.0

    def change_clock_if_required(self, time_of_received_msg: float):
        with self.lock:
            if self.clock < time_of_received_msg:
                self.idle_time = self.idle_time + (time_of_received_msg - self.clock)
                self.clock = time_of_received_msg

    def increment_clock(self, atomic_counter: int):
        with self.lock:
            self.clock = self.clock + atomic_counter

    def get_clock(self):
        with self.lock:
            return self.clock


class UnboundedBuffer:
    """
    msg synchronized buffer
    """
    def __init__(self):

        self.buffer = []

        self.cond = threading.Condition(threading.RLock())

    def insert(self, list_of_msgs):

        with self.cond:
            self.buffer.append(list_of_msgs)
            self.cond.notify_all()

    def extract(self):

        with self.cond:

            while len(self.buffer) == 0:
                self.cond.wait()

        ans = []

        for msg in self.buffer:

            if msg is None:

                return None

            else:

                ans.append(msg)

        self.buffer = []

        return ans

    def is_buffer_empty(self):

        return len(self.buffer) == 0


class Agent(threading.Thread, ABC):
    """
    represent a solver agent. the agent contain a simulation entity.
    The agent can receive and send messages.
    each agent has neighbours - an abstract object!
    can act as a thread
    # todo add threading and communication delay
    """
    def __init__(self, simulation_entity: Entity, t_now):

        # agent variables
        self.introduction_flag = None
        self.t_now = t_now
        self.neighbors = []  # all neighbors ids
        self.simulation_entity = simulation_entity  # all the information regarding the simulation entity
        self.inbox = None
        self.outbox = None
        self.mailer = None
        self._id = simulation_entity.getId()
        self.location = simulation_entity.location
        self.random_num = random.Random(self._id)


        # NCLO's
        self.atomic_counter = 0  # counter changes every computation
        self.NCLO = 0

    def meet_mailer(self, mailer_input):
        self.mailer = mailer_input

    def add_neighbour_id(self, id_):
        if self.simulation_entity.id_ not in self.neighbours_ids_list:
            self.neighbours_ids_list.append(id_)

    def remove_neighbour_id(self, id_):
        if self.simulation_entity.id_ in self.neighbours_ids_list:
            self.neighbours_ids_list.remove(id_)

    def set_inbox(self, inbox_input: UnboundedBuffer):
        self.inbox = inbox_input

    def set_outbox(self, outbox_input: UnboundedBuffer):
        self.outbox = outbox_input

    def update_neighbors(self):  # add neighbors agents id from simulation agent
        for i in self.simulation_entity.neighbors:
            self.add_neighbour_id(i)

    # @abc.abstractmethod
    # def reset(self):
    #     """
    #     reset fields of algorithm
    #     :return:
    #     """
    #     raise NotImplementedError

    @abc.abstractmethod
    def initialize(self):
        """
        initialize algorithm, the algorithms first iteration
        :return: None
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def compute(self):
        """
        after context was updated in method agent_receive_a_single_msg
        :return:
        """
        raise NotImplementedError()


    @abc.abstractmethod
    def send_msgs(self):
        """
        after computation broadcast the new information
        :return:
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def agent_receive_a_single_msg(self, msg):
        """
        updates incoming information
        :param msg:
        :return:
        """
        raise NotImplementedError()



    # @abc.abstractmethod
    # def check_termination(self):
    #     """
    #     has the agent terminated its run
    #     :return:
    #     """
    #     raise NotImplementedError()

    @staticmethod
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

    def introduce_to_neighbors(self):
        self.introduction_flag = True

    def __str__(self):
        return "id: " + str(self._id)

    def getId(self):
        return self._id


class Mailer(object):
    def __init__(self, problem_id, agents: [Agent]):
        # mailer variables
        self.problem_id = problem_id
        self.all_agents = agents

        # message variables
        self.msg_box = []  # all msg need to be delivered
        self.msg_receivers = {}

        self.number_of_messages_sent_total = 0
        self.current_time = 0.0 # for DSRM

    # called from agent to send msg
    def send_msg(self, msg):
        self.msg_box.append(msg)
        if message_debug:
            print("msg sent: "+msg.__str__())

    # initialize mailer and start run
    def initialize(self):
        for agent in self.all_agents:
            agent.meet_mailer(self)

    # sends msgs to agents
    def agents_receive_msgs(self):
        msgs_to_send = self.msg_box

        self.create_map_by_receiver(msgs_to_send)
        self.msg_box = [msg for msg in self.msg_box if msg not in msgs_to_send]

        for agent_id, msgs_for_agent in self.msg_receivers.items():
            receiver_agent = self.get_agent_by_id(agent_id)
            if message_debug:
                print(receiver_agent, " receives ", print_msgs(msgs_for_agent))
            self.number_of_messages_sent_total += len(msgs_for_agent)
            an_agent_receive_msgs(receiver_agent, msgs_for_agent)

    #  organize the messages in a map. key = receiver, values = msgs received
    def create_map_by_receiver(self, msgs_to_send):
        self.msg_receivers = {}
        for msg in msgs_to_send:
            receiver = msg.receiver
            if receiver not in self.msg_receivers:
                self.msg_receivers[receiver] = []
            self.msg_receivers[receiver].append(msg)

    # finds agent by id (from providers and requesters)
    def get_agent_by_id(self, agent_id):
        for agent in self.all_agents:
            if agent.getId() == agent_id:
                return agent
        else:
            return None


def print_msgs(msgs):
    strmsg = ""
    for msg in msgs:
        strmsg += str(msg) + " || "

    return strmsg


# sends messages to agent and agent reacts
def an_agent_receive_msgs(receiver_agent, msgs_per_agent):
    if receiver_agent is not None:
        for msg in msgs_per_agent:
            receiver_agent.agent_receive_a_single_msg(msg=msg)


# class Agent(threading.Thread, ABC):
#     """
#     list of abstract methods:
#     initialize_algorithm
#     --> how does the agent begins algorithm prior to the start() of the thread
#
#     set_receive_flag_to_true_given_msg(msgs):
#     --> given msgs received is agent going to compute in this iteration
#
#     get_is_going_to_compute_flag()
#     --> return the flag which determines if computation is going to occur
#
#     update_message_in_context(msg)
#     --> save msgs in agents context
#
#     compute
#     -->  use updated context to compute agents statues and
#
#     get_list_of_msgs
#     -->  create and return list of msgs
#
#     get_list_of_msgs
#     --> returns list of msgs that needs to be sent
#
#     set_receive_flag_to_false
#     --> after computation occurs set the flag back to false
#
#     measurements_per_agent
#     --> returns dict with key: str of measure, value: the calculated measure
#     """
#
#     def __init__(self, simulation_entity: Entity, t_now, is_with_timestamp=True):
#
#         # agent variables
#         self.t_now = t_now
#         self.neighbours_ids_list = []
#         self.simulation_entity = simulation_entity  # all the information regarding the simulation entity
#         self.inbox = None  # TODO update in solver
#         self.outbox = None
#         self.mailer = None
#
#         # treading variables
#         threading.Thread.__init__(self)
#         self.cond = threading.Condition(threading.RLock())  # TODO update in solver
#
#         # communication delay variables
#         self.is_with_timestamp = is_with_timestamp  # is agent using timestamp when msgs are received
#         self.timestamp_counter = 0  # For every msg sent the timestamp counter increases by one (see run method)
#         self.idle_time = 0
#         self.is_idle = True
#         self.msg_not_delivered_loss_timestamp_counter = 0
#         self.msg_received_counter = 0
#
#         # NCLO's
#         self.atomic_counter = 0  # counter changes every computation
#         self.NCLO = ClockObject()  # an instance of an object with
#
#     # communication delay methods
#     def reset_fields(self, t_now):
#         self.t_now = t_now
#         self.neighbours_ids_list = []
#         self.timestamp_counter = 0  # every msg sent the timestamp counter increases by one (see run method)
#         self.atomic_counter = 0  # counter changes every computation
#         self.NCLO = ClockObject()  # an instance of an object with
#         self.idle_time = 0
#         self.is_idle = True
#         self.cond = threading.Condition(threading.RLock())
#         self.inbox = None  # DONE
#         self.outbox = None
#         self.reset_additional_fields()
#         self.msg_not_delivered_loss_timestamp_counter = 0
#         self.msg_received_counter = 0
#
#     def update_cond_for_responsible(self, condition_input: threading.Condition):
#         self.cond = condition_input
#
#     def set_clock_object_for_responsible(self, clock_object_input):
#         self.NCLO = clock_object_input
#
#     # agent methods
#     def meet_mailer(self, mailer_input):
#         self.mailer = mailer_input
#
#     def add_neighbour_id(self, id_):
#         if self.simulation_entity.id_ not in self.neighbours_ids_list:
#             self.neighbours_ids_list.append(id_)
#
#     def remove_neighbour_id(self, id_):
#         if self.simulation_entity.id_ in self.neighbours_ids_list:
#             self.neighbours_ids_list.remove(id_)
#
#     def set_inbox(self, inbox_input: UnboundedBuffer):
#         self.inbox = inbox_input
#
#     def set_outbox(self, outbox_input: UnboundedBuffer):
#         self.outbox = outbox_input
#
#     @abc.abstractmethod
#     def initiate_algorithm(self):
#         """
#         before thread starts the action in this method will occur
#         :return:
#         """
#         raise NotImplementedError
#
#     @abc.abstractmethod
#     def measurements_per_agent(self):
#         """
#         NotImplementedError
#         :return: dict with key: str of measure, value: the calculated measure
#         """
#         raise NotImplementedError
#
#     # ---------------------- receive_msgs ----------------------
#
#     def receive_msgs(self, msgs: []):
#
#         for msg in msgs:
#
#             if self.is_with_timestamp:
#
#                 current_timestamp_from_context = self.get_current_timestamp_from_context(msg)
#
#                 if msg.timestamp > current_timestamp_from_context:
#                     self.set_receive_flag_to_true_given_msg(msg)
#                     self.update_message_in_context(msg)
#                     self.msg_received_counter += 1
#
#                 else:
#                     self.msg_not_delivered_loss_timestamp_counter += 1
#             else:
#                 self.set_receive_flag_to_true_given_msg(msg)
#                 self.update_message_in_context(msg)
#                 self.msg_received_counter += 1
#
#         self.update_agent_time(msgs)
#
#     @abc.abstractmethod
#     def set_receive_flag_to_true_given_msg(self, msg):
#
#         """
#         given msgs received is agent going to compute in this iteration?
#         set the relevant computation flag
#         :param msg:
#         :return:
#         """
#
#         raise NotImplementedError
#
#     @abc.abstractmethod
#     def get_current_timestamp_from_context(self, msg):
#
#         """
#         :param msg: use it to extract the current timestamp from the receiver
#         :return: the timestamp from the msg
#         """
#
#         raise NotImplementedError
#
#     @abc.abstractmethod
#     def update_message_in_context(self, msg):
#
#         '''
#         :param msg: msg to update in agents memory
#         :return:
#         '''
#
#         raise NotImplementedError
#
#     def update_agent_time(self, msgs):
#
#         """
#         :param msgs: list of msgs received simultaneously
#         """
#         max_time = self.get_max_time_of_msgs(msgs)
#         self.NCLO.change_clock_if_required(max_time)
#
#         # if self.NCLO <= max_time:
#         #    self.idle_time = self.idle_time + (max_time - self.NCLO)
#         #    self.NCLO = max_time
#
#     def get_max_time_of_msgs(self, msgs):
#         max_time = 0
#         for msg in msgs:
#             time_msg = msg.msg_time
#             if time_msg > max_time:
#                 max_time = time_msg
#
#         return max_time
#
#     # ---------------------- reaction_to_msgs ----------------------
#
#     def reaction_to_msgs(self):
#
#         with self.cond:
#             self.atomic_counter = 0
#             if self.get_is_going_to_compute_flag() is True:
#                 self.compute()  # atomic counter must change
#                 self.timestamp_counter = self.timestamp_counter + 1
#                 self.NCLO.increment_clock(atomic_counter=self.atomic_counter)
#                 self.send_msgs()
#                 self.set_receive_flag_to_false()
#
#     @abc.abstractmethod
#     def get_is_going_to_compute_flag(self):
#         """
#         :return: the flag which determines if computation is going to occur
#         """
#         raise NotImplementedError
#
#     @abc.abstractmethod
#     def compute(self):
#         """
#        After the context was updated by messages received, computation takes place
#        using the new information and preparation on context to be sent takes place
#         """
#         raise NotImplementedError
#
#     def send_msgs(self):
#         msgs = self.get_list_of_msgs_to_send()
#         for msg in msgs:
#             msg.add_current_NCLO(self.NCLO.clock)
#             msg.add_timestamp(self.timestamp_counter)
#             msg.is_with_perfect_communication = self.check_if_msg_should_have_perfect_communication(msg)
#         self.outbox.insert(msgs)
#
#     def check_if_msg_should_have_perfect_communication(self):
#         """
#         if both agent "sit" on the same computer them true
#         :return: bool
#         """
#         raise NotImplementedError
#
#     @abc.abstractmethod
#     def get_list_of_msgs_to_send(self):
#         """
#         create and return list of msgs to send
#         """
#         raise NotImplementedError
#
#     @abc.abstractmethod
#     def set_receive_flag_to_false(self):
#         """
#         after computation occurs set the flag back to false
#         :return:
#         """
#         raise NotImplementedError
#
#     def run(self) -> None:
#
#         while True:
#
#             self.set_idle_to_true()
#
#             msgs_list = self.inbox.extract()  # TODO when finish mailer
#
#             with self.cond:
#                 if msgs_list is None:
#                     break
#
#                 msgs = []
#                 for msg_list in msgs_list:
#                     for msg in msg_list:
#                         msgs.append(msg)
#                 self.set_idle_to_false()
#                 self.receive_msgs(msgs)
#                 self.reaction_to_msgs()
#
#     def set_idle_to_true(self):
#
#         with self.cond:
#             self.is_idle = True
#
#             self.cond.notify_all()
#
#     def set_idle_to_false(self):
#
#         with self.cond:
#             self.is_idle = False
#
#     def get_is_idle(self):
#         with self.cond:
#             while not self.is_idle:
#                 self.cond.wait()
#             return self.is_idle
#
#     @abc.abstractmethod
#     def reset_additional_fields(self):
#         raise NotImplementedError

# # todo - ask ben on this class and add relevant methods
# class Mailer(threading.Thread):
#
#     def __init__(self, f_termination_condition, f_global_measurements,
#                  f_communication_disturbance):
#         threading.Thread.__init__(self)
#
#         self.id_ = 0
#         self.msg_box = []
#
#         # function that returns dict=  {key: str of fields names, function of calculated fields}
#         self.f_global_measurements = f_global_measurements
#         # function that returns None for msg loss, or a number for NCLO delay
#         self.f_communication_disturbance = f_communication_disturbance
#
#         # function received by the user that determines when the mailer should stop iterating and kill threads
#         self.f_termination_condition = f_termination_condition
#
#         # TODO update in solver, key = agent, value = buffer  also points as an inbox for the agent
#         self.agents_outboxes = {}
#
#         # TODO update in solver, buffer also points as out box for all agents
#         self.inbox = None
#
#         # the algorithm agent created by the user will be updated in reset method
#         self.agents_algorithm = []
#
#         # mailer's clock
#         self.time_mailer = ClockObject()
#
#         self.measurements = {}
#
#         # message loss due to communication protocol
#         self.msg_not_delivered_loss_counter = 0
#
#         # message loss due to timestamp policy
#         self.msg_not_delivered_loss_timestamp_counter = 0
#
#         # message sent by players regardless to communication protocol
#         self.msg_sent_counter = 0
#
#         # messages that arrive to their destination
#         self.msg_received_counter = 0
#
#         self.last_time = 0
#         self.delta_time = 9999999
#
#     def get_allocation_dictionary(self):
#         pass
#
#     def reset(self,tnow):
#         global mailer_counter
#         self.msg_box = []
#         mailer_counter = mailer_counter + 1
#         self.id_ = mailer_counter
#         self.agents_outboxes = {}  # TODO update in allocate
#         self.inbox = None  # TODO update in solver
#         self.time_mailer = ClockObject()
#         self.measurements = {}
#         self.msg_not_delivered_loss_counter = 0
#         self.msg_not_delivered_loss_timestamp_counter = 0
#         self.msg_sent_counter = 0
#         self.msg_received_counter = 0
#
#         for key in self.f_global_measurements.keys():
#             self.measurements[key] = {}
#         self.measurements["Loss Counter"] = {}
#         self.measurements["Loss Timestamp Counter"] = {}
#         self.measurements["Message Sent Counter"] = {}
#         self.measurements["Message Received Counter"] = {}
#
#         for aa in self.agents_algorithm:
#             aa.reset_fields(tnow)
#
#         self.last_time = 0
#         self.delta_time = 0
#     def add_out_box(self, key: str, value: UnboundedBuffer):
#         self.agents_outboxes[key] = value
#
#     def set_inbox(self, inbox_input: UnboundedBuffer):
#         self.inbox = inbox_input
#
#
#     def remove_agent(self,entity_input):
#
#         for agent in self.agents_algorithm:
#             if agent.simulation_entity.id_ == entity_input.id_:
#                 self.agents_algorithm.remove(agent)
#                 return
#
#
#     def run(self) -> None:
#         for_check = {}
#         self.update_for_check(for_check)
#
#         """
#
#         create measurements
#
#         iterate for the first, in constractor all agents initiate their first "synchrnoized" iteration
#
#         iteration includes:
#
#         -  extract msgs from inbox: where the mailer waits for msgs to be sent
#
#         -  place messages in mailers message box with a withdrawn delay
#
#         -  get all the messages that have delivery times smaller in comperision to the the mailers clock
#
#         - deliver messages to the algorithm agents through their unbounded buffer
#
#
#
#         the run continue to iterate, and creates measurements at each iteration until the given termination condition is met
#
#         :return:
#
#         """
#
#         self.create_measurements()
#
#         self.mailer_iteration(with_update_clock_for_empty_msg_to_send=True)
#
#         while not self.f_termination_condition(self.agents_algorithm, self):
#
#
#             self.create_measurements()
#
#             self.self_check_if_all_idle_to_continue()
#
#             self.mailer_iteration(with_update_clock_for_empty_msg_to_send=False)
#
#             self.update_for_check(for_check)
#
#             if debug_timestamp:
#                 self.print_timestamps()
#         self.kill_agents()
#
#         for aa in self.agents_algorithm:
#             aa.join()
#
#     def create_measurements(self):
#         current_clock = self.time_mailer.get_clock()  # TODO check if immutable
#         #print("line 257 ",current_clock)
#         if debug_fisher_market:
#             print("******MAILER CLOCK", self.time_mailer.clock, "******")
#             self.print_fisher_input()
#             self.print_fisher_x()
#
#         for measurement_name, measurement_function in self.f_global_measurements.items():
#
#             measured_value = measurement_function(self.agents_algorithm)
#
#             self.measurements[measurement_name][current_clock] = measured_value
#
#
#
#         self.measurements["Loss Counter"][current_clock] = self.msg_not_delivered_loss_counter
#         self.measurements["Loss Timestamp Counter"][current_clock] = self.get_counter_sum_of_timestamp_loss_msgs_from_agents()
#         self.measurements["Message Sent Counter"][current_clock] = self.msg_sent_counter
#         self.measurements["Message Received Counter"][current_clock] = self.get_counter_sum_msg_received_counter_from_agents()
#
#     @staticmethod
#     def get_data_keys():
#         return ["Loss Counter","Loss Timestamp Counter","Message Sent Counter","Message Received Counter"]
#
#     def get_counter_sum_of_timestamp_loss_msgs_from_agents(self):
#         ans = 0
#         for aa in self.agents_algorithm:
#             ans+=aa.msg_not_delivered_loss_timestamp_counter
#         return ans
#
#     def get_counter_sum_msg_received_counter_from_agents(self):
#         ans = 0
#         for aa in self.agents_algorithm:
#             ans += aa.msg_received_counter
#         return ans
#
#     def kill_agents(self):
#
#         for out_box in self.agents_outboxes.values():
#             out_box.insert(None)
#
#     def self_check_if_all_idle_to_continue(self):
#
#         while self.inbox.is_buffer_empty() :
#
#             are_all_idle = self.are_all_agents_idle()
#
#             is_inbox_empty = self.inbox.is_buffer_empty()
#
#             is_msg_box_empty = len(self.msg_box) == 0
#
#             if are_all_idle and is_inbox_empty and not is_msg_box_empty:
#                 self.should_update_clock_because_no_msg_received()
#
#                 msgs_to_send = self.handle_delay()
#
#                 self.agents_receive_msgs(msgs_to_send)
#
#     def mailer_iteration(self, with_update_clock_for_empty_msg_to_send):
#
#
#         self.last_time = self.time_mailer.clock
#         msgs_from_inbox = self.inbox.extract()
#
#         self.place_msgs_from_inbox_in_msgs_box(msgs_from_inbox)
#
#         if with_update_clock_for_empty_msg_to_send:
#             self.should_update_clock_because_no_msg_received()
#
#         msgs_to_send = self.handle_delay()
#
#         self.agents_receive_msgs(msgs_to_send)
#
#         self.delta_time = self.time_mailer.clock-self.last_time
#
#     def handle_delay(self):
#
#         """
#
#         get from inbox all msgs with msg_time lower then mailer time
#
#         :return: msgs that will be delivered
#
#         """
#
#         msgs_to_send = []
#
#         new_msg_box_list = []
#         current_clock = self.time_mailer.get_clock()  # TODO check if immutable
#
#         for msg in self.msg_box:
#             if msg.msg_time <= current_clock:
#                 msgs_to_send.append(msg)
#             else:
#                 new_msg_box_list.append(msg)
#         self.msg_box = new_msg_box_list
#         return msgs_to_send
#
#     def place_msgs_from_inbox_in_msgs_box(self, msgs_from_inbox):
#
#         """
#
#         take a message from message box, and if msg is not lost, give it a delay and place it in msg_box
#
#         uses the function recieves as input in consturctor f_communication_disturbance
#
#         :param msgs_from_inbox: all messages taken from inbox box
#
#         :return:
#
#         """
#
#         for msgs in msgs_from_inbox:
#             if isinstance(msgs, list):
#                 for msg in msgs:
#                     self.place_single_msg_from_inbox_in_msgs_box(msg)
#             else:
#                 self.place_single_msg_from_inbox_in_msgs_box(msgs)
#
#     def place_single_msg_from_inbox_in_msgs_box(self,msg):
#         self.update_clock_upon_msg_received(msg)
#         e1 = self.get_simulation_entity(msg.sender)
#         e2 = self.get_simulation_entity(msg.receiver)
#
#         e1,e2 = self.get_responsible_agent(e1,e2)
#         communication_disturbance_output = self.f_communication_disturbance(e1,e2)
#         flag = False
#         self.msg_sent_counter += 1
#         if msg.is_with_perfect_communication:
#             self.msg_box.append(msg)
#             flag = True
#
#         if not flag and communication_disturbance_output is not None:
#             delay = communication_disturbance_output
#             delay = int(delay)
#
#             msg.set_time_of_msg(delay)
#             if debug_print_for_distribution:
#                 print(delay)
#             self.msg_box.append(msg)
#
#         if communication_disturbance_output is None:
#             self.msg_not_delivered_loss_counter +=1
#
#
#
#
#     def update_clock_upon_msg_received(self, msg: Msg):
#
#         """
#         prior for msg entering to msg box the mailer's clock is being updated
#         if the msg time is larger than
#         :param msg:
#         :return:
#
#         """
#
#         msg_time = msg.msg_time
#         self.time_mailer.change_clock_if_required(msg_time)
#         # current_clock = self.time_mailer.get_clock()  # TODO check if immutable
#         # if current_clock <= msg_time:
#         #    increment_by = msg_time-current_clock
#         #    self.time_mailer.increment_clock_by(input_=increment_by)
#
#     def agents_receive_msgs(self, msgs_to_send):
#
#         """
#         :param msgs_to_send: msgs that their delivery time is smaller then the mailer's time
#         insert msgs to relevant agent's inbox
#         """
#         msgs_dict_by_reciever_id = self.get_receivers_by_id(msgs_to_send)
#
#         for node_id, msgs_list in msgs_dict_by_reciever_id.items():
#             node_id_inbox = self.agents_outboxes[node_id]
#             node_id_inbox.insert(msgs_list)
#
#     def get_receivers_by_id(self, msgs_to_send):
#
#         '''
#
#         :param msgs_to_send: msgs that are going to be sent in mailer's current iteration
#
#         :return:  dict with key = receiver and value = list of msgs that receiver need to receive
#
#         '''
#
#         receivers_list = []
#
#         for msg in msgs_to_send:
#             receivers_list.append(msg.receiver)
#
#         receivers_set = set(receivers_list)
#
#         ans = {}
#
#         for receiver in receivers_set:
#
#             msgs_of_receiver = []
#
#             for msg in msgs_to_send:
#                 if msg.receiver == receiver:
#                     msgs_of_receiver.append(msg)
#             ans[receiver] = msgs_of_receiver
#
#         return ans
#
#     @staticmethod
#     def msg_with_min_time(msg: Msg):
#
#         return msg.msg_time
#
#     def should_update_clock_because_no_msg_received(self):
#
#         """
#
#         update the mailers clock according to the msg with the minimum time from the mailers message box
#
#         :return:
#
#         """
#
#         msg_with_min_time = min(self.msg_box, key=Mailer.msg_with_min_time)
#
#         msg_time = msg_with_min_time.msg_time
#         self.time_mailer.change_clock_if_required(msg_time)
#         # current_clock = self.time_mailer.get_clock()  # TODO check if immutable
#         # if msg_time > current_clock:
#         #    increment_by = msg_time-current_clock
#         #    self.time_mailer.increment_clock_by(input_=increment_by)
#
#     def are_all_agents_idle(self):
#
#         for a in self.agents_algorithm:
#
#             if not a.get_is_idle():
#                 return False
#
#         return True
#
#     def print_fisher_input(self):
#         print("-----R-----")
#
#         for p in  self.agents_algorithm:
#             if isinstance(p,PlayerAlgorithm):
#                 print()
#                 with p.cond:
#                     #print(p.simulation_entity.id_)
#                     for task, dict in p.r_i.items():
#                         for mission,util in dict.items():
#                             print(round(util.linear_utility,2),end=" ")
#
#         print()
#         print()
#
#         #print("-----R dict-----")
#
#         # for p in  self.agents_algorithm:
#         #     if isinstance(p,PlayerAlgorithm):
#         #         print()
#         #         with p.cond:
#         #             print(p.simulation_entity.id_,p.simulation_entity.abilities[0].ability_type)
#         #             for task, dict in p.r_i.items():
#         #                 for mission,util in dict.items():
#         #                     print("Task:",task,"Mission:",mission, "r_ijk:",round(util.linear_utility,2))
#         # print()
#         # print()
#
#     def print_fisher_x(self):
#
#         print("-----X-----")
#
#
#
#
#         for p in self.agents_algorithm:
#             if isinstance(p, TaskAlgorithm):
#
#                 with p.cond:
#                     for mission, dict in p.x_jk.items():
#                         print()
#                         for n_id,x in dict.items():
#                             if x is None:
#                                 print("None", end=" ")
#                             else:
#                                 print(round(x,4), end=" ")
#         print()
#
#     def get_simulation_entity(self, id_looking_for):
#         for a in self.agents_algorithm:
#             if a.simulation_entity.id_ == id_looking_for:
#                 return a.simulation_entity
#
#     def all_tasks_finish(self):
#         for aa in self.agents_algorithm:
#             if isinstance(aa,TaskAlgorithm):
#                 if not aa.is_finish_phase_II:
#                     return False
#         return True
#
#     def print_timestamps(self):
#         time_ = self.time_mailer.clock
#         print("---***",time_,"***---")
#
#         print("players:")
#         print("[",end="")
#         for agent in self.agents_algorithm:
#             if isinstance(agent,PlayerAlgorithm):
#                 print("{"+str(agent.simulation_entity.id_)+":"+str(agent.timestamp_counter)+"}", end="")
#         print("]")
#
#         print("tasks:")
#         print("[",end="")
#         for agent in self.agents_algorithm:
#             if isinstance(agent,TaskAlgorithm):
#                 print("{"+str(agent.simulation_entity.id_)+":"+str(agent.timestamp_counter)+"}", end="")
#         print("]")
#
#     def get_responsible_agent(self, e1, e2):
#         task = e1
#         agent = e2
#         if isinstance(e2, TaskSimple):
#             task = e2
#             agent = e1
#
#         return task.player_responsible,agent
#
#     def update_for_check(self, for_check):
#         for agent in self.agents_algorithm:
#             if isinstance(agent, TaskAlgorithm):
#                 for_check[agent.simulation_entity.id_] = agent.is_finish_phase_II # todo


# agents objects
