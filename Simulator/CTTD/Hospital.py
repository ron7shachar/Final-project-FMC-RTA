from Simulator.SimulationComponents import Entity


class Hospital(Entity):
    def __init__(self, _id, max_capacity, location=[0.0, 0.0], t_born=0.0):
        Entity.__init__(self, location=location, last_time_updated=t_born, _id=_id)
        self.current_capacity = max_capacity
        self.max_capacity = max_capacity
        self.casualties = [] # list of the casualties in the hospital

    def add_casualties(self, casualties: list):
        self.current_capacity -= len(casualties)
        self.casualties.append(casualties)
