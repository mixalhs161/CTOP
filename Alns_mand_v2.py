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
        """Άθροισμα profits όλων των routed πελατών."""
        return sum(
            self.model.nodes[nid].profit
            for route in self.routes_as_ids
            for nid in route
            if nid != 0
        )

    def total_cost(self):
        """Άθροισμα cost όλων των routes (επανυπολογισμός on-demand)."""
        return sum(
            self.model.cost_matrix[route[i]][route[i + 1]]
            for route in self.routes_as_ids
            for i in range(len(route) - 1)
        )
    @staticmethod
    def from_solution(solution, model):
        """
        Δημιουργεί CtopState από Solution object του Solver.
        Παραλείπει empty routes. Filtrάρει mandatory από το unassigned.
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

    # ---------- Helpers για insertion (χρησιμοποιούνται από repair operators) ----------

    def route_load(self, route_idx):
        """Συνολικό demand του route (μη συμπεριλαμβανομένου depot)."""
        return sum(
            self.model.nodes[nid].demand
            for nid in self.routes_as_ids[route_idx]
            if nid != 0
        )

    def route_cost(self, route_idx):
        """Συνολικό κόστος διαδρομής του route."""
        route = self.routes_as_ids[route_idx]
        return sum(
            self.model.cost_matrix[route[i]][route[i + 1]]
            for i in range(len(route) - 1)
        )

    def insertion_cost(self, cust_id, route_idx, pos):
        """
        Cost change αν τοποθετήσω τον cust_id στη θέση pos του route.
        Δηλαδή c(A, cust) + c(cust, B) − c(A, B).
        """
        route = self.routes_as_ids[route_idx]
        A = route[pos - 1]
        B = route[pos]
        cost_added = (self.model.cost_matrix[A][cust_id]
                    + self.model.cost_matrix[cust_id][B])
        cost_removed = self.model.cost_matrix[A][B]
        return cost_added - cost_removed

    def feasible_insertion(self, cust_id, route_idx, pos):
        """Ελέγχει αν η insertion παραβιάζει capacity ή t_max."""
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
        """
        Composite objective improvement: M·profit − cost_change.
        Συνεπές με τον constructive και την objective() του state.
        """
        return (self.BIG_NUMBER * self.model.nodes[cust_id].profit
                - self.insertion_cost(cust_id, route_idx, pos))
#Function in order to tranform and return  the State object to Solution object
def state_to_solution(state):
    """
    Μετατρέπει CtopState σε Solution object.
    Χρειάζεται για το validate / plot / write που δουλεύουν με Solution.
    """
    sol = Solution()

    # Reset isRouted flags
    for node in state.model.nodes:
        node.isRouted = False

    for route_ids in state.routes_as_ids:

        # Φτιάξε Route object
        route = Route(
            depot=state.model.nodes[0],
            t_max=state.model.t_max,
            capacity=state.model.capacity
        )

        # Αντικατάστησε το default [depot, depot] με την πραγματική ακολουθία
        route.sequenceOfNodes = [state.model.nodes[nid] for nid in route_ids]

        # Υπολογισμός cost
        route.cost = sum(
            state.model.cost_matrix[route_ids[i]][route_ids[i+1]]
            for i in range(len(route_ids) - 1)
        )

        # Υπολογισμός load
        route.load = sum(
            state.model.nodes[nid].demand
            for nid in route_ids if nid != 0
        )

        # Υπολογισμός profit
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
    Destroy operator: αφαιρεί τυχαία N optional πελάτες από τα routes.
    Mandatory ΔΕΝ αφαιρούνται ποτέ (Approach B).

    N = 15% των τρέχοντων routed optional, με ελάχιστο 1.
    """
    #Candidates for removal
    candidates = [
        nid
        for route in state.routes_as_ids
        for nid in route
        if nid != 0
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

    # 5. Πρόσθεσε στους unassigned
    state.unassigned.update(selected_ids)

    return state
def shaw_removal(state, rnd_state):
    state = state.copy()
    """
    Shaw / Related removal: αφαιρεί έναν seed πελάτη + τους N-1 πιο συγγενείς.
    Συγγένεια μετριέται με γεωγραφική απόσταση (απλοποιημένη εκδοχή).

    Mandatory ΔΕΝ αφαιρούνται ποτέ (Approach B).
    """
    # 1. Συλλογή routed optional
    routed_optional = [
        nid for route in state.routes_as_ids
        for nid in route
        if nid != 0
    ]

    if len(routed_optional) < 2:
        return state

    # 2. Πόσους θα αφαιρέσω συνολικά (μαζί με τον seed)
    degree_of_destruction = 0.15
    n_to_remove = max(2, int(degree_of_destruction * len(routed_optional)))
    n_to_remove = min(n_to_remove, len(routed_optional))

    # 3. Διάλεξε τυχαία τον seed
    seed_idx = rnd_state.integers(0, len(routed_optional))
    seed = routed_optional[seed_idx]

    # 4. Υπολογισμός συγγένειας όλων των υπολοίπων με τον seed
    others = [nid for nid in routed_optional if nid != seed]
    relatedness_scores = [
        (state.model.cost_matrix[seed][nid], nid)
        for nid in others
    ]

    # 5. Ταξινόμηση: πιο συγγενείς πρώτοι (μικρότερη απόσταση)
    relatedness_scores.sort(key=lambda x: x[0])

    # 6. Επιλογή N-1 από τους 2(N-1) πιο συγγενείς (με τυχαιότητα)
    pool_size = min(2 * (n_to_remove - 1), len(relatedness_scores))
    pool = relatedness_scores[:pool_size]

    selected_indices = rnd_state.choice(
        len(pool), size=n_to_remove - 1, replace=False
    )
    selected_ids = {pool[i][1] for i in selected_indices}
    selected_ids.add(seed)   # μην ξεχάσεις τον seed!

    # 7. Αφαίρεση από routes & update unassigned
    state.routes_as_ids = [
        [nid for nid in route if nid not in selected_ids]
        for route in state.routes_as_ids
    ]
    state.unassigned.update(selected_ids)

    return state

def worst_removal(state, rnd_state):
    state = state.copy()
    """
    Destroy operator: αφαιρεί optional πελάτες με τη μικρότερη contribution.
    Contribution = M·profit − detour_cost στην τρέχουσα θέση.
    Συνεπές με το objective z = M·p − c.

    Mandatory ΔΕΝ αφαιρούνται ποτέ (Approach B).
    """
    # 1. Υπολογισμός contribution για κάθε routed optional
    candidates = []   # list of (contribution, node_id)

    for route in state.routes_as_ids:
        for pos in range(1, len(route) - 1):   # παραλείπει depot σε αρχή/τέλος
            nid = route[pos]


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

    # 2. Ταξινόμηση από τον χειρότερο προς τον καλύτερο
    candidates.sort(key=lambda x: x[0])

    #How many to remove
    degree_of_destruction = rnd_state.uniform(0.1, 0.35)        # λίγο πιο επιθετικό από random
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
    route_costs = [state.route_cost(i) for i in range(len(state.routes_as_ids))]
    route_loads = [state.route_load(i) for i in range(len(state.routes_as_ids))]

    # ========== ΦΑΣΗ 1: Mandatory με regret ==========
    while True:
        mandatory_unrouted = [
            nid for nid in state.unassigned
            if state.model.nodes[nid].isMandatory
        ]
        if not mandatory_unrouted:
            break

        best_choice = None

        for cust_id in mandatory_unrouted:
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

    # ========== ΦΑΣΗ 2: Optional με regret ==========
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

    # ========== ΦΑΣΗ 1: Mandatory first ==========
    while True:
        mandatory_unrouted = [
            nid for nid in state.unassigned
            if state.model.nodes[nid].isMandatory
        ]
        if not mandatory_unrouted:
            break   # όλοι οι mandatory τοποθετήθηκαν, πάμε στη Φάση 2

        best = None
        for cust_id in mandatory_unrouted:
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
            break   # mandatory δεν χωράει πουθενά — infeasible state

        _, cust_id, r_idx, pos = best
        state.routes_as_ids[r_idx].insert(pos, cust_id)
        state.unassigned.discard(cust_id)

        # Cache update
        A = state.routes_as_ids[r_idx][pos - 1]
        B = state.routes_as_ids[r_idx][pos + 1]
        ic = (state.model.cost_matrix[A][cust_id]
              + state.model.cost_matrix[cust_id][B]
              - state.model.cost_matrix[A][B])
        route_costs[r_idx] += ic
        route_loads[r_idx] += state.model.nodes[cust_id].demand

    # ========== ΦΑΣΗ 2: Optional ==========
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

        A = state.routes_as_ids[r_idx][pos - 1]
        B = state.routes_as_ids[r_idx][pos + 1]
        ic = (state.model.cost_matrix[A][cust_id]
              + state.model.cost_matrix[cust_id][B]
              - state.model.cost_matrix[A][B])
        route_costs[r_idx] += ic
        route_loads[r_idx] += state.model.nodes[cust_id].demand

    return state
#Statistics
def print_operator_stats(result):


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
    alns.add_destroy_operator(random_removal)
    alns.add_destroy_operator(shaw_removal)
    alns.add_destroy_operator(worst_removal)
    alns.add_repair_operator(greedy_repair)
    alns.add_repair_operator(regret_2_repair)

    destroyOperators = len(alns.destroy_operators)
    repairOperators = len(alns.repair_operators)

    # Selection
    select = AlphaUCB(scores=[10, 5, 2, 0], alpha=0.5,
                            num_destroy=destroyOperators,
                            num_repair=repairOperators)
    #Acceptance
    accept = SimulatedAnnealing(start_temperature=80,
                                    end_temperature=0.01, step=0.99)


    alns.on_best(lambda s, r: print(f"  New Best: profit = {s.total_profit()}"))

    # Iterate
    result = alns.iterate(init_state, select, accept, MaxIterations(iterations))
    print_operator_stats(result)
    solution = state_to_solution(result.best_state)
    return solution

