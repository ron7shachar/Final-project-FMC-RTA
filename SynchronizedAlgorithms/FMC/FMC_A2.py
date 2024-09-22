from Solver.SOMAOP.BasicSOMAOP import *
from SynchronizedAlgorithms.SynchronizedSolver import VariableAssignment
from Simulator.SimulationComponents import ServiceProvider
from Solver.SOMAOP.BasicSOMAOP import SR, SP
dbug = True
BIG = 99999


class FmcSR(SR):
    def __init__(self, simulation_entity: ServiceRequester, bid_type, t_now=None, algo_version=0):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SR.__init__(self, simulation_entity=simulation_entity, bid_type=bid_type, t_now=t_now,
                    algorithm_version=algo_version)
        self.small = 0.00000001
        self.dPrice = {}  # The stabilization index
        self.mail_in = {}  # {sp : {tip : message }} \{'earliestTime','bid'} ,
        self.mail_out = {}  # {sp : {tip : message }} \{'allocation','startTime'} , R{"location","skills" W,}
        self.arrival_time = {}  # vector of earliest times [skill]
        self.stable = False
        self.msg_tipe = 'HSM'

        #### local view
        # self.neighbors = self.neighbors "A"
        self.allocations = {}  # matrices of allocations [sp*skill] "X"
        self.bids = {}  # matrices of  bids [sp*skill] "B"
        self.price = {}  # {skill : price } "P"
        self.earliestTimes = {}  # matrices of earliest times [sp*skill] ""




    def initialize(self):
        pass
    def reset_msgs(self):self.mail_in = { sp:{'tipe':'HSM'}for sp in self.neighbors}

    ####################################### msgs
    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
        self.bids[msg.sender] = mail_in['bids']

        if 'earliestTimes' in mail_in:
            self.earliestTimes[msg.sender] = mail_in['earliestTimes']
    def create_msg(self):
        if self.msg_tipe == 'HSM':
            for sp in self.neighbors:
                self.mail_out[sp] = {}
                self.mail_out[sp]['tipe'] = self.msg_tipe
                self.mail_out[sp]['offers'] = self.compute_initial_offers()
                self.mail_out[sp]['skills'] = self.skills_needed
                self.mail_out[sp]['location'] = self.location
        else:
            for sp in self.allocations.keys():
                self.mail_out[sp] = {}
                self.mail_out[sp]['tipe'] = self.msg_tipe
                self.mail_out[sp]["allocation"] = self.allocations[sp]
                if self.arrival_time:
                    self.mail_out[sp]['startTime'] = self.arrival_time
        self.msg_tipe = 'SM'
    def send_msgs(self):
        if not self.stable:
            if self.allocations:
                for sp in self.allocations:
                    self.mailer.send_msg(OfferMessage(self._id, sp, self.mail_out[sp]))
            else:
                for sp in self.neighbors:
                    self.mailer.send_msg(OfferMessage(self._id, sp, self.mail_out[sp]))

    ##################################### compute
    def compute(self):
        if not self.stable:
            self.compute_price()
            self.check_if_it_stable()
            self.compute_allocations()
            # self.updateEarliestTimes()
            if self.earliestTimes:
                self.compute_earliestTimes()
            self.create_msg()
    def compute_price(self):
        self.dPrice = copy.deepcopy(self.price)
        self.price = {}
        for sp in self.bids.keys():
            for skillBid in self.bids[sp].keys():
                if skillBid in self.price.keys():
                    self.price[skillBid] += self.bids[sp][skillBid]
                else:
                    self.price[skillBid] = self.bids[sp][skillBid]
    def compute_allocations(self):
        for sp in self.bids:
            self.allocations[sp] = {}
            for skills in self.bids[sp].keys():
                self.NCLO+=1
                if self.bids[sp][skills] != 0:
                    allocation = self.bids[sp][skills] / self.price[skills]
                    if allocation > self.small:
                        self.allocations[sp][skills] = allocation
    def compute_initial_offers(self):
        offers = {}
        for skill in self.skills_needed:
            offers[skill] = VariableAssignment(
                provider=None,
                requester=self,
                skill=skill,
                location=self.location,
                amount=None,
                duration=0.0,
                arrival_time=None,
                leaving_time=None,
                utility=None,
                mission=None,
                max_capacity=None,
                accept=False)
        return offers
    def compute_earliestTimes(self):
        self.arrival_time = {}
        for sp in self.earliestTimes.keys():
            for skill in self.earliestTimes[sp].keys():
                if skill in self.arrival_time.keys():
                    if self.earliestTimes[sp][skill] > self.arrival_time[skill]:
                        self.arrival_time[skill] = self.earliestTimes[sp][skill]
                else:
                    self.arrival_time[skill] = self.earliestTimes[sp][skill]

    ############################################## sub function
    def check_if_it_stable(self):
        if not self.dPrice : return
        for skill in self.dPrice:
            if abs(self.dPrice[skill] - self.price[skill]) > self.small:
                self.stable = False
                return
        self.stable = True
class FmcSP(SP):
    def __init__(self, simulation_entity: ServiceProvider, t_now=None, algo_version=0, accept_offers_version=0,
                 alfa=0.7):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SP.__init__(self, simulation_entity=simulation_entity, t_now=t_now, algorithm_version=algo_version)
        self.raf = 0.001  # xij<e
        self.R = {}  # {SR_id:VALUE}
        self.srs = {}  ## list of all the sr that ask for a service { "id" : id , "skill": W(SR,skill) ,"location": location}
        self.mail_in = {}  # {sp : {tip : message }} / {'allocation','startTime'} , R{'skills'}
        self.mail_out = {}  # {sp : {tip : message }} / {'earliestTime','bid'} ,
        self.skills = simulation_entity.skills  ## list of all the needed skills

        self.allocations = {}  # matrices of allocations [sr*skill]
        self.normalize = {}
        self.bids = {}  # matrices of  bids [sr*skill]
        self.earliestTimes = {}  # matrices of earliest times [sr*skill]

        self.offers = {}
        self.last_time = self.t_now
        self.first = None
        self.old_schedule = []
        self.is_commit = False
    def initialize(self):
        pass

    ############################################ msges
    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
        self.mail_in[msg.sender] = {}
        self.mail_in[msg.sender]['tipe'] = mail_in['tipe']
        if self.mail_in[msg.sender]['tipe'] == "SM":
            if 'allocation' in mail_in:
                # self.allocations[msg.sender] = self.filter_skills(mail_in['allocation'])
                self.allocations[msg.sender] = mail_in['allocation']
                if 'startTime' in mail_in.keys():
                    self.mail_in[msg.sender]['startTime'] = mail_in['startTime']

        else:
            self.srs[msg.sender] = self.filter_skills(mail_in['skills'])
            self.mail_in[msg.sender]['offers'] = mail_in['offers']
            self.mail_in[msg.sender]['location'] = mail_in['location']

            self.srs[msg.sender] = {"skills": mail_in['skills'], 'location': mail_in['location']}
    def create_msg(self):
        self.mail_out = {}
        for sr in self.bids.keys():
            self.mail_out[sr] = {}
            self.mail_out[sr]["bids"] = self.bids[sr]
            if self.mail_in[sr]['tipe'] == "SM":
                self.mail_out[sr]['earliestTimes'] = self.earliestTimes[sr]
    def send_msgs(self):
        for sr in self.bids.keys():
            self.mailer.send_msg(OfferMessage(self._id, sr, self.mail_out[sr]))
   ############################################# compute
    def compute(self):
        self.compute_bid()
        self.create_initial_schedule()
        self.calculate_start_and_end_times()
        self.update_sr()
        self.create_msg()
    def compute_bid(self):
        sumXS = {}
        for sr in self.allocations.keys():
            if self.mail_in[sr]['tipe'] == 'SM':
                for skill in self.allocations[sr].keys():
                    if skill in sumXS:
                        sumXS[skill] += self.allocations[sr][skill] * self.R[sr][skill]
                    else:
                        sumXS[skill] = self.allocations[sr][skill] * self.R[sr][skill]

        for sr in self.allocations.keys():
            if self.mail_in[sr]['tipe'] == 'SM':
                for skill in self.allocations[sr].keys():
                    self.bids[sr][skill] = self.allocations[sr][skill] * self.R[sr][skill] / sumXS[skill]
    def create_initial_schedule(self):
        self.schedule = []
        for sr in self.bids.keys():
            for skill in self.bids[sr].keys():
                self.NCLO += 1
                if skill in self.allocations[sr]:
                    self.schedule.append(SPSchedule(
                        self,
                        sr,
                        skill,
                        self.last_time,
                        self.allocations[sr][skill] * self.srs[sr]['skills'][skill], #fl זמן הפעולה
                        ########      W(SR,SKILL),
                        self.bids[sr][skill]/self.srs[sr]['skills'][skill]))

        self.schedule = sorted(self.schedule, key=lambda sp_schedule: sp_schedule.important)
        for i in range(len(self.schedule)):
            sp_ = self.schedule[i]
            if not self.schedule:
                sp_.update_startTime(self.last_time + sp_.travel_from())
            else:
                sp_.update_startTime(self.schedule[i - 1].leaving_time + sp_.travel_from(self.schedule[i - 1]))
            self.earliestTimes[sp_.requester] = {sp_.skill: sp_.arrival_time}
    def calculate_start_and_end_times(self):
        schedule_cooperative = []
        schedule_uncooperative = []
        schedule_uncooperative_left = []
        for sp_schedule in self.schedule:
            if 'startTime' in self.mail_in[sp_schedule.requester].keys():
                self.NCLO += 1
                if self.bids[sp_schedule.requester][sp_schedule.skill] >= 1:  ################   if cooperative
                    if sp_schedule.skill in self.mail_in[sp_schedule.requester]['startTime'].keys():
                        sp_schedule.update_startTime(self.mail_in[sp_schedule.requester]['startTime'][sp_schedule.skill])
                        schedule_cooperative.append(sp_schedule)
                else:
                    schedule_uncooperative.append(sp_schedule)
        schedule_cooperative = sorted(schedule_cooperative, key=lambda sp_schedule: sp_schedule.arrival_time)

        for i in range(1, len(schedule_cooperative)):
            travel_time = schedule_cooperative[i - 1].travel_to(schedule_cooperative[i])
            distant_time = schedule_cooperative[i].arrival_time - schedule_cooperative[i - 1].leaving_time + travel_time
            schedule_cooperative[i].travel_time = travel_time
            if distant_time < 0:
                schedule_cooperative[i].update_startTime(schedule_cooperative[i - 1].leaving_time + travel_time)


        for sp_schedule in schedule_uncooperative:
            for i in range(0, len(schedule_cooperative) - 1):
                if i == 0:
                    travel_time = schedule_cooperative[i].travel_from()
                    distant_time = schedule_cooperative[i].arrival_time - self.last_time + travel_time
                    sub_distant_time = (sp_schedule.travel_from() + sp_schedule.travel_to(schedule_cooperative[i])
                                        + sp_schedule.leaving_time - sp_schedule.arrival_time)
                else:
                    travel_time = schedule_cooperative[i].travel_from(schedule_cooperative[i - 1])
                    distant_time = schedule_cooperative[i].arrival_time - schedule_cooperative[i].leaving_time + travel_time
                    sub_distant_time = (sp_schedule.travel_from(schedule_cooperative[i - 1]) + sp_schedule.travel_to(
                        schedule_cooperative[i])
                                        + sp_schedule.leaving_time - sp_schedule.arrival_time)

                if sub_distant_time < distant_time:
                    schedule_cooperative.insert(i, sp_schedule)
                    sp_schedule.travel_time = travel_time
                    break
            else:
                if schedule_cooperative:
                    if not schedule_uncooperative_left:
                        sp_schedule.travel_time = sp_schedule.travel_from(schedule_cooperative[-1])
                        # print(schedule_cooperative[-1].leaving_time + sp_schedule.travel_time)
                        sp_schedule.update_startTime(schedule_cooperative[-1].leaving_time + sp_schedule.travel_time)
                    else:
                        sp_schedule.travel_time = sp_schedule.travel_from(schedule_uncooperative_left[-1])
                        sp_schedule.update_startTime(schedule_cooperative[-1].leaving_time + sp_schedule.travel_time)

                schedule_uncooperative_left.append(sp_schedule)

        self.schedule = schedule_cooperative + schedule_uncooperative_left
        # print( 'schedule of sp :' , self._id)
        # print(self.schedule)
    def update_sr(self):  # fl     חישוב הR
        for sr in self.mail_in.keys():
            if self.mail_in[sr]['tipe'] == 'HSM':
                self.offers[sr] = {}
                for skill in self.mail_in[sr]['offers'].keys():
                    offer = self.mail_in[sr]['offers'][skill]
                    offer.provider = self
                    offer.arrival_time = self.last_time + self.travel_time(self.location, offer.location)
                    offer.amount = 10
                    offer.leaving_time = self.last_time + BIG
                    offer.accept = True
                    self.offers[sr][skill] = offer
                self.compute_R()

    def compute_R(self):  # fl     חישוב הR
        sumR = {}
        for sr in self.offers.keys():
            self.R[sr] = {}
            for skill in self.offers[sr].keys():
                self.R[sr][skill] = self.offers[sr][skill].requester.simulation_entity.calc_converge_bid_to_offer(skill,
                                                                                                                  self.offers[
                                                                                                                      sr][
                                                                                                                      skill])
                if skill in sumR:
                    sumR[skill] += self.R[sr][skill]
                else:
                    sumR[skill] = self.R[sr][skill]

        for sr in self.R.keys():
            for skill in self.R[sr].keys():
                if skill in sumR:
                    self.R[sr][skill] = self.R[sr][skill] / sumR[skill]


    ########################################### sub function
    def filter_skills(self, skills):
        new_skills = {}
        for skill in skills.keys():
            if skill in self.skills:
                new_skills[skill] = skills[skill]
        return new_skills

    def commit(self, sr, skill):
        if skill not in self.skills:
            self.is_commit = False
            return
        print(self.offers[sr])
        self.offers[sr].pop(skill)
        self.bids[sr].pop(skill)
        if not self.offers[sr]: self.offers.pop(sr)
        if not self.bids[sr]: self.bids.pop(sr)
        self.last_time = self.first.leaving_time
        self.location = self.first.location
        self.old_schedule.append(self.first)
        self.first = None
        for sr in self.offers:
            self.mail_out[sr]["bids"] = self.bids[sr]
            for skill in self.offers[sr]:
                offer = self.offers[sr][skill]
                offer.arrival_time = self.last_time + self.travel_time(self.location, offer.location)
        self.compute_R()

    def get_schedule(self): return self.old_schedule + self.schedule



class SPSchedule(VariableAssignment):
    def __init__(self, sp, sr, skill, arrival_time, leaving_time, important):
        VariableAssignment.__init__(self,
                                    provider=sp,
                                    requester=sr,
                                    skill=skill,
                                    location=sp.srs[sr]['location'],
                                    amount=None,
                                    duration=0.0,
                                    arrival_time=None,
                                    leaving_time=None,
                                    utility=None,
                                    mission=None,
                                    max_capacity=None,
                                    accept=True)

        # self.skill = skill
        # self.sp = sp
        # self.id = sr

        travel_time = self.travel_from()
        self.travel_time = travel_time
        self.arrival_time = arrival_time + travel_time
        self.leaving_time = leaving_time
        self.important = important
        # self.location = sp.srs[sr]['location']
    def __repr__(self):
        return f"sp :  {self.provider} sr : {self.requester} skill : {self.skill} startTime :  {self.arrival_time}"

    def update_startTime(self, new_star_time):
        self.leaving_time = new_star_time + self.leaving_time - self.arrival_time
        self.arrival_time = new_star_time
        self.travel_time = None


    def travel_to(self, to):
        return self.provider.travel_time(self.location, to.location)

    def travel_from(self, from_=None):
        if from_ is None:
            return self.provider.travel_time(self.provider.location, self.location)
        else:
            return self.provider.travel_time(from_.location, self.location)