import copy

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
        self.small = 0.00001
        self.dPrice = {}  # The stabilization index
        self.arrival_time = {}  # vector of earliest times [skill]
        self.stable = False

        #### local view
        # self.neighbors = self.neighbors "A"
        self.allocations = {}  # matrices of allocations [sp*skill] "X"
        self.bids = {}  # matrices of  bids [sp*skill] "B"
        self.price = {}  # {skill : price } "P"
        self.earliestTimes = {}  # matrices of earliest times [sp*skill] ""
        self.type = 'HSM'
        self.skills = list(self.skills_needed.keys())
        self.first = {}
        self.Rs = {}
        self.initial_offers={}

    def initialize(self):
        pass

    ####################################### msgs
    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
        match mail_in['type']:
            case "R":
                self.type = "R"
                self.Rs[msg.sender] = mail_in['bids']
        self.bids[msg.sender] = mail_in['bids']

        # if mail_in['type'] == 'HSM' or mail_in['type'] == 'commit':self.Rs[msg.sender] = mail_in['bids']
        # # if mail_in['type'] == 'commit':
        # #     self.msg_type = 'commit'
        # else:self.bids[msg.sender] = mail_in['bids']
        # # if 'first' in mail_in.keys() : self.first[msg.sender] = mail_in['first']
        # if 'earliestTimes' in mail_in:
        #     self.earliestTimes[msg.sender] = mail_in['earliestTimes']

    def send_msgs(self) :
        # if self.skills and not self.stable:
        mail_out = {}
        match self.type:
            case "SM":
                for sp in self.arrival_time:
                    mail_out['type'] = "SM"
                    if sp in self.allocations: mail_out["allocation"] = self.allocations[sp]
                    mail_out['startTime'] = self.arrival_time
                    self.mailer.send_msg(OfferMessage(self._id, sp, mail_out))
            case "HSM":
                for sp in self.neighbors:
                    mail_out['type'] = "HSM"
                    mail_out['offers'] = self.initial_offers
                    mail_out['skills'] = self.skills_needed
                    mail_out['location'] = self.location
                    self.mailer.send_msg(OfferMessage(self._id, sp, mail_out))
            case "R":
                for sp in self.allocations:
                    mail_out['type'] = "SM"
                    mail_out["allocation"] = self.allocations[sp]
                    mail_out["sr"] = self._id
                    self.mailer.send_msg(OfferMessage(self._id, sp, mail_out))




    ##################################### compute
    def compute(self):
        if not self.skills:self.stable = True
        if not self.stable:
            if self.type == "R":
                self.compute_price()
                self.compute_allocations()
            # self.check_if_it_stable()
            # # self.updateEarliestTimes()
            # if self.earliestTimes:
            #     self.compute_earliestTimes()
            # self.create_msg()
            self.reset_view()

    def compute_price(self):
        self.dPrice = copy.deepcopy(self.price)
        self.price = {}
        for sp in self.bids.keys():
            for skillBid in self.bids[sp].keys():
                if skillBid in self.price.keys():
                    # if self.msg_type == 'commit':self.bids[sp][skillBid] = self.Rs[sp][skillBid]
                    self.price[skillBid] += self.bids[sp][skillBid]
                else:
                    self.price[skillBid] = self.bids[sp][skillBid]

    def compute_allocations(self):
        self.allocations = {}
        for sp in self.bids.keys():
            for skill in self.bids[sp].keys():
                self.NCLO += 1
                if self.bids[sp][skill] != 0 and skill in self.skills:
                    allocation = self.bids[sp][skill] / self.price[skill]
                    if allocation > self.small:
                        if sp not in self.allocations: self.allocations[sp] = {}
                        self.allocations[sp][skill] = allocation


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
        self.initial_offers = offers

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
        self.commit = {}
        if not self.dPrice: return
        for skill in self.dPrice:
            if skill in self.price:
                if abs(self.dPrice[skill] - self.price[skill]) > self.small:
                    self.stable = False
                    return
        self.stable = True  ####################
        return  #############################

        # true_skill = []
        # false_skill = []
        # for sp in self.first.keys():
        #     for skill in self.first[sp].keys():
        #         if skill not in false_skill and skill in self.skills:
        #             if self.first[sp][skill]:
        #                 if skill not in true_skill:
        #                     true_skill.append(skill)
        #             else:
        #                 if skill in true_skill:
        #                     true_skill.remove(skill)
        #                 false_skill.append(skill)
        # if true_skill:
        #     self.skills.remove(true_skill[0])
        #     for sp in self.first.keys():
        #         self.commit[sp] = true_skill[0]



    def reset_view(self):
        self.bids = {}


class FmcSP(SP):
    def __init__(self, simulation_entity: ServiceProvider, t_now=None, algo_version=0, accept_offers_version=0,
                 alfa=0.7):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SP.__init__(self, simulation_entity=simulation_entity, t_now=t_now, algorithm_version=algo_version)
        self.raf = 0.001  # xij<e
        self.R = {}  # {SR_id:VALUE}
        self.skills = simulation_entity.skills  ## list of all the needed skills

        self.srs = {}  ## list of all the sr that ask for a service { "id" : id , "skill": W(SR,skill) ,"location": location}
        self.offers = {}
        self.last_time = self.t_now
        self.old_schedule = []
        self.msg_tips = {}
        self.schedule = []
        self.first = None

        self.bids = {}  # matrices of  bids [sr*skill]
        self.arrival_times = {}

        self.allocations = {}  # matrices of allocations [sr*skill]
        self.normalize = {}
        self.join_arrival_times = {}  # matrices of earliest times [sr*skill]
        self.commits = {}
        self.msg_typs = {}
        self.earliestTimes = {}
        self.final_schedule = []
        self.startTime = {}
        self.commits ={}
        self.old_final_schedule = []
        self.type = 'HSM'
        self.is_stable= 0

    def initialize(self):
        pass

    ############################################ msges
    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
        match mail_in['type']:
            case "SM":
                print(self._id, msg.sender , mail_in['allocation'] )
                self.allocations[msg.sender] = mail_in['allocation']
                if 'startTime' in mail_in.keys():
                    self.startTime[msg.sender] = mail_in['startTime']

            case "HSM":
                self.srs[msg.sender] = {"skills": self.filter_skills(mail_in['skills']), 'location': mail_in['location'],
                                        'offers': mail_in['offers']}
                self.type = 'HSM'
            case 'commit': pass

    def send_msgs(self):
        if self.type != "SM":
            for sr in self.R:
                mail_out = {}
                mail_out["bids"] = self.R[sr]
                mail_out['type'] = "R"
                self.mailer.send_msg(OfferMessage(self._id, sr, mail_out))

        # firsts = {}
        # for offer in self.final_schedule:
        #     if offer.requester not in firsts.keys(): firsts[offer.requester] = {}
        #     if self.first is None:
        #         firsts[offer.requester][offer.skill] = False
        #     else:
        #         firsts[offer.requester][offer.skill] = (self.first == offer)

        # # for sr in self.bids.keys():
        # #
        # #     mail_out = {}
        # #
        # #     mail_out['type'] = self.type
        # #
        # #     mail_out["bids"] = self.bids[sr]
        # #     if sr in self.earliestTimes.keys():
        # #         mail_out['earliestTimes'] = self.earliestTimes[sr]
        #
        #     # if sr in firsts.keys():
        #     #     mail_out['first'] = firsts[sr]
        #
        #     self.mailer.send_msg(OfferMessage(self._id, sr, mail_out))
        self.type = "SM"
    ############################################# compute
    def compute(self):
        if self.type == "SM":self.compute_bid()
        # self.create_initial_schedule()
        # # self.is_commit()
        # self.calculate_start_and_end_times()
        self.compute_R()
        self.reset_view()

    def compute_bid(self):

        self.bids = {}
        sumXS = {}
        for sr in self.allocations.keys():

            for skill in self.allocations[sr].keys():
                if skill in sumXS:
                    sumXS[skill] += self.allocations[sr][skill] * self.R[sr][skill]
                else:
                    sumXS[skill] = self.allocations[sr][skill] * self.R[sr][skill]
        for sr in self.allocations.keys():
            for skill in self.allocations[sr].keys():
                if sumXS[skill] != 0:
                    if sr not in self.bids: self.bids[sr] = {}
                    self.bids[sr][skill] = self.allocations[sr][skill] * self.R[sr][skill] / sumXS[skill]
    def create_initial_schedule(self):
        self.schedule = []
        for sr in self.bids.keys():
            for skill in self.bids[sr].keys():
                self.NCLO += 1
                self.schedule.append(SPSchedule(
                    self,
                    sr,
                    skill,
                    self.last_time,
                    self.allocations[sr][skill] * self.srs[sr]['skills'][skill],  # fl זמן הפעולה
                    ########      W(SR,SKILL),
                    self.bids[sr][skill] / self.srs[sr]['skills'][skill],
                    self.allocations[sr][skill]))

        self.schedule = sorted(self.schedule, key=lambda sp_schedule: sp_schedule.important)
        # self.final_schedule = self.schedule
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
        if not self.old_schedule:
            self.final_schedule = self.schedule
        else:
            for sp_schedule in self.old_schedule:
                self.NCLO += 1
                if sp_schedule.requester in self.startTime.keys():
                    if round(sp_schedule.allocation, 4) <= 1:  ################   if cooperative
                        if sp_schedule.skill in self.startTime[sp_schedule.requester].keys():
                            sp_schedule.update_startTime(self.startTime[sp_schedule.requester][sp_schedule.skill])
                            schedule_cooperative.append(sp_schedule)
                            continue

                schedule_uncooperative.append(sp_schedule)
            schedule_cooperative = sorted(schedule_cooperative, key=lambda sp_schedule: sp_schedule.arrival_time)
            self.final_schedule = schedule_cooperative + schedule_uncooperative

            for i in range(1, len(schedule_cooperative)):
                travel_time = schedule_cooperative[i - 1].travel_to(schedule_cooperative[i])
                distant_time = schedule_cooperative[i].arrival_time - schedule_cooperative[
                    i - 1].leaving_time + travel_time
                schedule_cooperative[i].travel_time = travel_time
                if distant_time < 0:
                    schedule_cooperative[i].update_startTime(schedule_cooperative[i - 1].leaving_time + travel_time)

            schedule_uncooperative_left = copy.copy(schedule_uncooperative)
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
                        schedule_uncooperative_left.remove(sp_schedule)
                        sp_schedule.travel_time = travel_time
                        break

                    if schedule_cooperative:
                        if not schedule_uncooperative_left:
                            sp_schedule.travel_time = sp_schedule.travel_from(schedule_cooperative[-1])

                            sp_schedule.update_startTime(schedule_cooperative[-1].leaving_time + sp_schedule.travel_time)
                        else:
                            sp_schedule.travel_time = sp_schedule.travel_from(schedule_uncooperative_left[-1])
                            sp_schedule.update_startTime(schedule_cooperative[-1].leaving_time + sp_schedule.travel_time)


            self.final_schedule = schedule_cooperative + schedule_uncooperative_left
            print(len(self.final_schedule))



    def compute_R(self):  # fl     חישוב הR

        if self.type == 'HSM':
            for sr in self.srs.keys():
                for skill in self.srs[sr]['skills'].keys():
                    offer = self.srs[sr]['offers'][skill]
                    offer.provider = self
                    offer.arrival_time = self.last_time + self.travel_time(self.location, offer.location)
                    offer.amount = 10
                    offer.leaving_time = self.last_time + BIG
                    offer.accept = True
                    if sr not in self.offers: self.offers[sr] = {}
                    self.offers[sr][skill] = offer

        for sr in self.commits.keys():
            if sr == self.first.requester and self.commits[sr] == self.first.skill:
                self.type = 'commit'


                # self.commit(sr, self.commits[sr])

        if self.type == 'HSM' or self.type == 'commit':
            for sr in self.offers.keys():
                for skill in self.offers[sr].keys():
                        offer = self.offers[sr][skill]
                        if sr not in self.R : self.R[sr] = {}
                        self.R[sr][skill] = offer.requester.simulation_entity.calc_converge_bid_to_offer(skill, offer)





    ###########################################  commit


    def is_commit(self):
        for sr in self.commits.keys():
            if sr == self.first.requester and self.commits[sr] == self.first.skill:
                self.commit(sr,self.commits[sr])
    def commit(self, sr, skill):
        self.type = "commit"
        self.is_stable = 0

        self.location = self.first.location
        self.last_time = self.first.leaving_time

        self.old_final_schedule.append(self.first)
        self.final_schedule.pop(self.final_schedule.index(self.first))

        self.offers[sr].pop(skill)
        if not self.offers[sr]:self.offers.pop(sr)

        for sr in self.offers.keys():
            for skill in self.offers[sr].keys():
                offer = self.offers[sr][skill]
                offer.arrival_time = self.last_time + self.travel_time(self.location, offer.location)

    ########################################### sub function
    def reset_view(self):
        # self.startTime = {}
        self.allocations = {}
        self.old_schedule = copy.copy(self.schedule)
        # if self.is_stable>1:
        #     if self.final_schedule:
        #         self.first = self.final_schedule[0]
        #     else:
        #         self.first = None
        # else:self.is_stable+=1
        # self.commits = {}
    def filter_skills(self, skills):
        new_skills = {}
        for skill in skills.keys():
            if skill in self.skills:
                new_skills[skill] = skills[skill]
        return new_skills
    def get_schedule(self):return self.old_final_schedule + self.final_schedule


class SPSchedule(VariableAssignment):
    def __init__(self, sp, sr, skill, arrival_time, leaving_time, important, allocation):
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
                                    accept=True
                                    )

        # self.skill = skill
        # self.sp = sp
        # self.id = sr

        self.allocation = allocation
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
