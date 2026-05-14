import copy
import numpy as np
import numpy.random as rnd
import matplotlib.pyplot as plt
from alns import ALNS
from alns.accept import RecordToRecordTravel
from alns.select import RouletteWheel, AlphaUCB, MABSelector, SegmentedRouletteWheel, RandomSelect
from alns.accept import SimulatedAnnealing, HillClimbing
from alns.stop import MaxIterations
from CTOPSolver import Solution, Route
class CtopState:
    BIG_NUMBER = 10**4   # Same as Solver

    def __init__(self, routes_as_ids, unassigned, model):
        self.routes_as_ids = routes_as_ids   # List[List[int]]
        self.unassigned = unassigned          # set[int] — μόνο optional
        self.model = model
    def objective(self):
        return -(self.BIG_NUMBER * self.total_profit() - self.total_cost())

    def copy(self):
        """Deep copy της δομής. Model παραμένει shared reference."""
        return CtopState(
            [list(r) for r in self.routes_as_ids],
            set(self.unassigned),
            self.model
        )
    def total_profit(self):
        """Sum of profits"""
        return sum(
            self.model.nodes[nid].profit
            for route in self.routes_as_ids
            for nid in route
            if nid != 0
        )

    def total_cost(self):
        """Sum of costs"""
        return sum(
            self.model.cost_matrix[route[i]][route[i + 1]]
            for route in self.routes_as_ids
            for i in range(len(route) - 1)
        )
    @staticmethod
    def from_solution(solution, model):
        """
        Creating a CtopState object from a Solution object
        """
        routes_as_ids = [
            [node.id for node in route.sequenceOfNodes]
            for route in solution.routes
            if len(route.sequenceOfNodes) > 2
        ]
        unassigned = {
            n.id for n in model.nodes
            if not n.isDepot and not n.isMandatory and not n.isRouted
        }
        return CtopState(routes_as_ids, unassigned, model)

    # ---------- Helpers for insertion (Used by repair operators) ----------

    def route_load(self, route_idx):
        """Total route demand"""
        return sum(
            self.model.nodes[nid].demand
            for nid in self.routes_as_ids[route_idx]
            if nid != 0
        )

    def route_cost(self, route_idx):
        """Total route cost"""
        route = self.routes_as_ids[route_idx]
        return sum(
            self.model.cost_matrix[route[i]][route[i + 1]]
            for i in range(len(route) - 1)
        )

    def insertion_cost(self, cust_id, route_idx, pos):

        route = self.routes_as_ids[route_idx]
        A = route[pos - 1]
        B = route[pos]
        cost_added = (self.model.cost_matrix[A][cust_id]
                    + self.model.cost_matrix[cust_id][B])
        cost_removed = self.model.cost_matrix[A][B]
        return cost_added - cost_removed

    def feasible_insertion(self, cust_id, route_idx, pos):
        """Cheking if we have a feasible insertion"""
        # Capacity
        new_load = self.route_load(route_idx) + self.model.nodes[cust_id].demand
        if new_load > self.model.capacity:
            return False
        # Time
        new_cost = self.route_cost(route_idx) + self.insertion_cost(cust_id, route_idx, pos)
        if new_cost > self.model.t_max:
            return False
        return True

    def move_cost(self, cust_id, route_idx, pos):

        return (self.BIG_NUMBER * self.model.nodes[cust_id].profit
                - self.insertion_cost(cust_id, route_idx, pos))
#Function in order to tranform and return  the State object to Solution object
def state_to_solution(state):
    """
    Transforming a CtopState Object to a Solution object
    """
    sol = Solution()

    # Reset isRouted flags
    for node in state.model.nodes:
        node.isRouted = False

    for route_ids in state.routes_as_ids:
        # Παράλειψε empty routes (μόνο [0, 0])


        route = Route(
            depot=state.model.nodes[0],
            t_max=state.model.t_max,
            capacity=state.model.capacity
        )
        route.sequenceOfNodes = [state.model.nodes[nid] for nid in route_ids]

        route.cost = sum(
            state.model.cost_matrix[route_ids[i]][route_ids[i+1]]
            for i in range(len(route_ids) - 1)
        )

        route.load = sum(
            state.model.nodes[nid].demand
            for nid in route_ids if nid != 0
        )

        route.profit = sum(
            state.model.nodes[nid].profit
            for nid in route_ids if nid != 0
        )

        # Mark customers as routed
        for nid in route_ids:
            if nid != 0:
                state.model.nodes[nid].isRouted = True

        sol.routes.append(route)


    sol.totalprofit = sum(r.profit for r in sol.routes)
    sol.totalcost = sum(r.cost for r in sol.routes)

    return sol
#-----------DESTROY-OPERATORS----------#
def random_removal(state, rnd_state):
    state = state.copy()
    """
    Destroy operator:Removing N optianl nodes from the route,Mandatory nodes never
    removed

    N = 15% of the current routed optional.
    """
    #Candidates for removal
    candidates = [
        nid
        for route in state.routes_as_ids
        for nid in route
        if nid != 0 and not state.model.nodes[nid].isMandatory
    ]

    if not candidates:
        return state

    #How many to remove
    degree_of_destruction = 0.15
    n_to_remove = max(1, int(degree_of_destruction * len(candidates)))
    n_to_remove = min(n_to_remove, len(candidates))

    # Random selection
    selected_indices = rnd_state.choice(
        len(candidates), size=n_to_remove, replace=False
    )
    selected_ids = {candidates[i] for i in selected_indices}

    #
    state.routes_as_ids = [
        [nid for nid in route if nid not in selected_ids]
        for route in state.routes_as_ids
    ]

    # 5. Adding them to unassigned
    state.unassigned.update(selected_ids)

    return state
def shaw_removal(state, rnd_state):
    state = state.copy()

    routed_optional = [
        nid for route in state.routes_as_ids
        for nid in route
        if nid != 0 and not state.model.nodes[nid].isMandatory
    ]

    if len(routed_optional) < 2:
        return state

    # Destruction degree
    degree_of_destruction = 0.1
    n_to_remove = max(2, int(degree_of_destruction * len(routed_optional)))
    n_to_remove = min(n_to_remove, len(routed_optional))

    # Seed selection
    seed_idx = rnd_state.integers(0, len(routed_optional))
    seed = routed_optional[seed_idx]

    # Normalization factors
    others = [nid for nid in routed_optional if nid != seed]


    distances = [state.model.cost_matrix[seed][nid] for nid in others]
    demand_diffs = [abs(state.model.nodes[seed].demand - state.model.nodes[nid].demand) for nid in others]
    profit_diffs = [abs(state.model.nodes[seed].profit - state.model.nodes[nid].profit) for nid in others]

    # Normalization (max-normalization)
    max_d = max(distances) if distances else 1
    max_dem = max(demand_diffs) if demand_diffs else 1
    max_p = max(profit_diffs) if profit_diffs else 1
    max_d = max_d if max_d > 0 else 1
    max_dem = max_dem if max_dem > 0 else 1
    max_p = max_p if max_p > 0 else 1


    alpha = 1   # distance
    beta = 0.5    # demand
    gamma = 0.5   # profit

    # relatedness scores
    relatedness_scores = []
    for i, nid in enumerate(others):
        score = (alpha * distances[i] / max_d
                 + beta * demand_diffs[i] / max_dem
                 + gamma * profit_diffs[i] / max_p)
        relatedness_scores.append((score, nid))


    relatedness_scores.sort(key=lambda x: x[0])

    # Pool-based selection
    pool_size = min(2 * (n_to_remove - 1), len(relatedness_scores))
    pool = relatedness_scores[:pool_size]

    selected_indices = rnd_state.choice(
        len(pool), size=n_to_remove - 1, replace=False
    )
    selected_ids = {pool[i][1] for i in selected_indices}
    selected_ids.add(seed)

    # Removal
    state.routes_as_ids = [
        [nid for nid in route if nid not in selected_ids]
        for route in state.routes_as_ids
    ]
    state.unassigned.update(selected_ids)

    return state

def worst_removal(state, rnd_state):
    state = state.copy()
    """
    Destroy operator: Removes optianal nodes with smaller contrbibution
    Contribution = M·profit − detour_cost .
    Mandatory never removed.
    """
    candidates = []   # list of (contribution, node_id)
    for route in state.routes_as_ids:
        for pos in range(1, len(route) - 1):
            nid = route[pos]
            if state.model.nodes[nid].isMandatory:
                continue

            A = route[pos - 1]
            B = route[pos + 1]
            detour = (state.model.cost_matrix[A][nid]
                      + state.model.cost_matrix[nid][B]
                      - state.model.cost_matrix[A][B])
            profit = state.model.nodes[nid].profit
            contribution = state.BIG_NUMBER * profit - detour
            candidates.append((contribution, nid))

    if not candidates:
        return state

    candidates.sort(key=lambda x: x[0])
    #How many to remove
    degree_of_destruction = rnd_state.uniform(0.1, 0.35)
    n_to_remove = max(1, int(degree_of_destruction * len(candidates)))
    n_to_remove = min(n_to_remove, len(candidates))


    # From 2N nodes take the N worst
    pool_size = min(2 * n_to_remove, len(candidates))
    pool = candidates[:pool_size]

    selected_indices = rnd_state.choice(
        len(pool), size=n_to_remove, replace=False
    )
    selected_ids = {pool[i][1] for i in selected_indices}

    # Updating the route
    state.routes_as_ids = [
        [nid for nid in route if nid not in selected_ids]
        for route in state.routes_as_ids
    ]
    state.unassigned.update(selected_ids)

    return state
#-----------REPAIR-OPERATORS---------#
def regret_2_repair(state, rnd_state):
    state = state.copy()
    # Cache route stats
    route_costs = [state.route_cost(i) for i in range(len(state.routes_as_ids))]
    route_loads = [state.route_load(i) for i in range(len(state.routes_as_ids))]

    while state.unassigned:
        best_choice = None

        for cust_id in state.unassigned:
            cust_demand = state.model.nodes[cust_id].demand
            cust_profit = state.model.nodes[cust_id].profit
            insertions = []

            for route_idx, route in enumerate(state.routes_as_ids):
                if route_loads[route_idx] + cust_demand > state.model.capacity:
                    continue

                for pos in range(1, len(route)):
                    A = route[pos - 1]
                    B = route[pos]
                    ic = (state.model.cost_matrix[A][cust_id]
                          + state.model.cost_matrix[cust_id][B]
                          - state.model.cost_matrix[A][B])
                    if route_costs[route_idx] + ic > state.model.t_max:
                        continue

                    mc = state.BIG_NUMBER * cust_profit - ic
                    insertions.append((mc, route_idx, pos))

            if not insertions:
                continue

            insertions.sort(key=lambda x: -x[0])
            best_mc, best_r_idx, best_pos = insertions[0]

            if len(insertions) >= 2:
                regret = best_mc - insertions[1][0]
            else:
                regret = float('inf')

            if best_choice is None or regret > best_choice[0]:
                best_choice = (regret, cust_id, best_r_idx, best_pos)

        if best_choice is None:
            break

        # Insertion + update cache
        _, cust_id, r_idx, pos = best_choice
        state.routes_as_ids[r_idx].insert(pos, cust_id)
        state.unassigned.discard(cust_id)

        A = state.routes_as_ids[r_idx][pos - 1]
        B = state.routes_as_ids[r_idx][pos + 1]
        ic = (state.model.cost_matrix[A][cust_id]
              + state.model.cost_matrix[cust_id][B]
              - state.model.cost_matrix[A][B])
        route_costs[r_idx] += ic
        route_loads[r_idx] += state.model.nodes[cust_id].demand

    return state

def greedy_repair(state, rnd_state):
    state = state.copy()
    route_costs = [state.route_cost(i) for i in range(len(state.routes_as_ids))]
    route_loads = [state.route_load(i) for i in range(len(state.routes_as_ids))]

    while state.unassigned:
        best = None

        for cust_id in state.unassigned:
            cust_demand = state.model.nodes[cust_id].demand
            cust_profit = state.model.nodes[cust_id].profit

            for route_idx, route in enumerate(state.routes_as_ids):
                if route_loads[route_idx] + cust_demand > state.model.capacity:
                    continue

                for pos in range(1, len(route)):
                    A = route[pos - 1]
                    B = route[pos]
                    ic = (state.model.cost_matrix[A][cust_id]
                          + state.model.cost_matrix[cust_id][B]
                          - state.model.cost_matrix[A][B])

                    if route_costs[route_idx] + ic > state.model.t_max:
                        continue

                    mc = state.BIG_NUMBER * cust_profit - ic
                    if best is None or mc > best[0]:
                        best = (mc, cust_id, route_idx, pos)

        if best is None:
            break

        _, cust_id, r_idx, pos = best
        state.routes_as_ids[r_idx].insert(pos, cust_id)
        state.unassigned.discard(cust_id)

        # Update cache
        A = state.routes_as_ids[r_idx][pos - 1]
        B = state.routes_as_ids[r_idx][pos + 1]
        ic = (state.model.cost_matrix[A][cust_id]
              + state.model.cost_matrix[cust_id][B]
              - state.model.cost_matrix[A][B])
        route_costs[r_idx] += ic
        route_loads[r_idx] += state.model.nodes[cust_id].demand

    return state

#Statistics
def print_operator_stats(result, seed):
    print(f"\n--- Operator Statistics (Seed {seed}) ---")

    print(f"\n  Destroy Operators:")
    print(f"  {'Name':<20} {'Total':>7} {'Best':>6} {'Better':>7} {'Accept':>7} {'Reject':>7}")
    for op_name, counts in result.statistics.destroy_operator_counts.items():
        total = sum(counts)
        n_best, n_better, n_accept, n_reject = (int(c) for c in counts)
        print(f"  {op_name:<20} {total:>7} {n_best:>6} {n_better:>7} {n_accept:>7} {n_reject:>7}")

    print(f"\n  Repair Operators:")
    print(f"  {'Name':<20} {'Total':>7} {'Best':>6} {'Better':>7} {'Accept':>7} {'Reject':>7}")
    for op_name, counts in result.statistics.repair_operator_counts.items():
        total = sum(counts)
        n_best, n_better, n_accept, n_reject = (int(c) for c in counts)
        print(f"  {op_name:<20} {total:>7} {n_best:>6} {n_better:>7} {n_accept:>7} {n_reject:>7}")

def run_alns(model, solution, iterations):

    rng = rnd.default_rng(4)
    # Initial state
    init_state = CtopState.from_solution(solution, model)
    # ALNS setup
    alns = ALNS(rng)
    #Destroy operators
    alns.add_destroy_operator(random_removal)
    alns.add_destroy_operator(shaw_removal)
    alns.add_destroy_operator(worst_removal)
    #Repair operators
    alns.add_repair_operator(greedy_repair)
    alns.add_repair_operator(regret_2_repair)

    destroyOperators = len(alns.destroy_operators)
    repairOperators = len(alns.repair_operators)

    # Selection
    select = AlphaUCB(scores=[10, 5, 2, 0], alpha=0.50,
                            num_destroy=destroyOperators,
                            num_repair=repairOperators)
    #Acceptance
    accept = SimulatedAnnealing(start_temperature=80,
                                    end_temperature=0.01, step=0.99)


    alns.on_best(lambda s, r: print(f"  New Best: profit = {s.total_profit()}"))

    # Iterate
    result = alns.iterate(init_state, select, accept, MaxIterations(iterations))
    solution = state_to_solution(result.best_state)
    return solution

