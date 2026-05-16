from Parser import *
from dataclasses import dataclass
from typing import List
import random
import copy

class Route:
    """
    A single vehicle route: a sequence of nodes starting and ending at the depot.

    Structure:  [depot, customer₁, customer₂, …, customerₖ, depot]
    The depot appears at both ends — representing departure and return.

    Attributes
    ----------
    sequenceOfNodes : list[Node]
        Ordered node visit sequence.  Always starts and ends with the depot.
    cost : float
        Total travel distance of this route.
    max_distance : float
        Distance budget.  The route is feasible only if cost ≤ max_distance.
    profit : float
        Sum of profits of all CUSTOMERS on this route (excluding depot).
    """

    def __init__(self, depot, t_max, capacity):
        self.sequenceOfNodes = []
        self.sequenceOfNodes.append(depot)
        self.sequenceOfNodes.append(depot)
        self.cost = 0
        self.t_max = t_max
        self.profit = 0
        self.load = 0
        self.capacity = capacity

class Solution:
    def __init__(self):
        self.routes = []
        self.totalprofit = 0
        self.totalcost = 0

class CustomerInsertAllPositions:
    def __init__(self):
        self.customer = None
        self.route = None
        self.movecost = -10**9
        self.costchange = 10**9
        self.profit = 0
        self.position = None

class SwapBetweenUnrouted_Routed:
    def __init__(self):
        self.originRoutePosition = None
        self.originNodePosition = None
        self.costChange = None
        self.profitChange = None
        self.moveCost = None
        self.node = None

    def Initialize(self):
        self.originRoutePosition = None
        self.originNodePosition = None
        self.costChange = None
        self.profitChange = None
        self.moveCost = -10**9
        self.node = None

class Solver:

    def __init__(self, m):
        self.model = m
        self.num_nodes: int =  m.num_nodes
        self.vehicles: int = m.vehicles
        self.capacity: int = m.capacity
        self.t_max: float = m.t_max
        self.nodes: List[Node] = m.nodes
        self.cost_matrix: List[List[float]] = m.cost_matrix
        self.depot = m.nodes[0]
        self.BIG_NUMBER = 10**4
        self.rcl_size = 4
        self.bonus = {}
        self.mandatory_penalties = 10**5


    def solve(self,enforce_mandatory):

        seeds=[4, 8, 15, 16, 23, 42]
        self.enforce_mandatory = enforce_mandatory
        self.SetRoutedFlagToFalseForAllNodes()
        if self.enforce_mandatory:
            self.MinimumInsertionsMandatory()
            from Alns_mand import run_alns
            improved_solution = run_alns(self.model, self.sol,7000)
            self.sol = improved_solution
            return self.sol
        else:
            seeds = [4, 8, 15, 16, 23, 42]
            solutions = []
            for seed in seeds:
                self.SetRoutedFlagToFalseForAllNodes()
                current_res = self.MinimumInsertionsWithRcl(seed)
                solutions.append(current_res)
                print(f"Seed: {seed} | Profit: {current_res.totalprofit}")
            solutions.sort(key=lambda x: x.totalprofit, reverse=True)
            self.sol = solutions[0]
            return self.sol


    def SetRoutedFlagToFalseForAllNodes(self):
       #Mark every node as unrouted
        for node in self.nodes:
            node.isRouted = False
    #-----------NO_MANDATORY INSTANCE AREA-----------#
    def MinimumInsertionsWithRcl(self,seed):
        random.seed(seed)
        sol = Solution()
        for _ in range(self.vehicles):
            new_route = Route(self.depot,self.t_max, self.capacity)
            sol.routes.append(new_route)
        unvisited_customers = [n for n in self.nodes if not n.isDepot and not n.isRouted]
        while unvisited_customers:
            best_insertion = CustomerInsertAllPositions()
            self.IdentifyBestCustomerInsertionwithRcl(sol,best_insertion, unvisited_customers, seed)
            if best_insertion.customer is not None:
                self.ApplyBestCustomerInsertionwithRcl(sol,best_insertion, unvisited_customers)
            else:
                break

        return sol

    def IdentifyBestCustomerInsertionwithRcl(self,sol, best_insertion,unvisited_customers,seed):
        rcl = []
        for customer in unvisited_customers:
            for route in sol.routes:
                for i in range(0, len(route.sequenceOfNodes)-1):
                    A = route.sequenceOfNodes[i]
                    B = route.sequenceOfNodes[i+1]
                    cost_added = self.cost_matrix[A.id][customer.id] +self.cost_matrix[customer.id][B.id]
                    cost_removed = self.cost_matrix[A.id][B.id]
                    cost_change = cost_added - cost_removed
                    profit_change = customer.profit
                    move_cost =(self.BIG_NUMBER * profit_change) - cost_change
                    #Check feasibility
                    if self.ViolateTimeConstraint(route, cost_change):
                        continue
                    if self.ViolateCapacityConstraint(route, customer):
                        continue
                    #Rcl insertion
                    if len(rcl) < self.rcl_size:
                        new_tup = (customer, route, move_cost,cost_change, profit_change, i+1)
                        rcl.append(new_tup)
                        rcl.sort(key=lambda x:x[2],reverse=True)
                    else:
                        if move_cost > rcl[-1][2]:
                            rcl.pop()
                            new_tup = (customer, route, move_cost, cost_change, profit_change, i+1)
                            rcl.append(new_tup)
                            rcl.sort(key=lambda x:x[2], reverse=True)
        if len(rcl) == 0:
            return None
        else:
            chosen = random.choice(rcl)
            best_insertion.customer     = chosen[0]
            best_insertion.route        = chosen[1]
            best_insertion.move_cost    = chosen[2]
            best_insertion.cost_change  = chosen[3]
            best_insertion.profit       = chosen[4]
            best_insertion.position     = chosen[5]

    def ApplyBestCustomerInsertionwithRcl(self,sol,best_insertion,univisited_customers):
        #Unpacking the object
        customer = best_insertion.customer
        univisited_customers.remove(customer)
        route = best_insertion.route
        position = best_insertion.position
        route.sequenceOfNodes.insert(position, customer)
        route.load += customer.demand
        route.profit += customer.profit
        route.cost += best_insertion.cost_change
        customer.isRouted = True
        sol.totalcost += best_insertion.cost_change
        sol.totalprofit += customer.profit




    #-----------Mandatory_instance Area-----------#
    def InitializeBonuses(self):
        self.bonus = {
            n.id: {r_idx: 0 for r_idx in range(self.vehicles)}
            for n in self.nodes if n.isMandatory
        }
    def MinimumInsertionsMandatory(self):
        self.InitializeBonuses()
        self.sol = Solution()
        for _ in range(self.vehicles):
            new_route = Route(self.depot,self.t_max, self.capacity)
            self.sol.routes.append(new_route)
        unvisited_customers = [n for n in self.nodes if not n.isDepot]
        while unvisited_customers:
            best_insertion = CustomerInsertAllPositions()
            self.IdentifyBestCustomerInsertionMandatory(best_insertion, unvisited_customers)
            if best_insertion.customer is not None:
                self.ApplyBestCustomerInsertion(best_insertion, unvisited_customers)
            else:
                break
        print(self.sol.totalprofit)
        return self.sol

    def IdentifyBestCustomerInsertionMandatory(self,best_insertion, unvisited_customers):
        for customer in unvisited_customers:
            for route in self.sol.routes:
                for i in range(0, len(route.sequenceOfNodes)-1):
                    A = route.sequenceOfNodes[i]
                    B = route.sequenceOfNodes[i+1]
                    cost_added = self.cost_matrix[A.id][customer.id] +self.cost_matrix[customer.id][B.id]
                    cost_removed = self.cost_matrix[A.id][B.id]
                    cost_change = cost_added - cost_removed
                    profit_change = customer.profit
                    r_idx = self.sol.routes.index(route)
                    if customer.isMandatory:
                        move_cost = (self.BIG_NUMBER * profit_change) - cost_change \
                        + self.mandatory_penalties * self.bonus[customer.id][r_idx]
                    else:
                        move_cost = (self.BIG_NUMBER * profit_change) - cost_change
                    #Check feasibility
                    if self.ViolateTimeConstraint(route, cost_change):
                        continue
                    if self.ViolateCapacityConstraint(route, customer):
                        continue
                    if move_cost > best_insertion.movecost:
                        best_insertion.customer     = customer
                        best_insertion.route        = route
                        best_insertion.movecost     = move_cost
                        best_insertion.cost_change  = cost_change
                        best_insertion.profit       = profit_change
                        best_insertion.position     = i+1


    def ApplyBestCustomerInsertion(self,best_insertion,unvisited_customers):
        #Unpacking the object
        customer = best_insertion.customer
        unvisited_customers.remove(customer)
        route = best_insertion.route
        position = best_insertion.position
        route.sequenceOfNodes.insert(position, customer)
        route.load += customer.demand
        route.profit += customer.profit
        route.cost += best_insertion.cost_change
        customer.isRouted = True
        self.sol.totalcost += best_insertion.cost_change
        self.sol.totalprofit += customer.profit
        for n in unvisited_customers:
            if n.isMandatory:
                for r_idx in range(self.vehicles):
                    if self.sol.routes[r_idx] != best_insertion.route:
                        self.bonus[n.id][r_idx] += 1


    def VerifyProfitCalculation(self):

        """
        Recomputes profit from scratch and compares with stored values.
        Catches bugs where route.profit / sol.totalprofit drift from reality.
        """
        print("\n--- Profit Verification ---")
        inconsistencies = []
        recomputed_total = 0

        for idx, route in enumerate(self.sol.routes):
            # Επανυπολογισμός profit του route
            recomputed = sum(
                n.profit for n in route.sequenceOfNodes if not n.isDepot
            )
            recomputed_total += recomputed

            # Σύγκριση με stored
            if recomputed != route.profit:
                inconsistencies.append(
                    f"Route {idx}: stored={route.profit}, recomputed={recomputed}"
                )

        # Σύγκριση συνολικού profit
        if recomputed_total != self.sol.totalprofit:
            inconsistencies.append(
                f"Total: stored={self.sol.totalprofit}, recomputed={recomputed_total}"
            )

        if inconsistencies:
            print("✗ Profit inconsistencies found:")
            for issue in inconsistencies:
                print(f"  - {issue}")
        else:
            print(f"✓ Profit consistent. Total = {recomputed_total}")
#------Area of functions designed to check if we have a constraint violation------#
    def  ViolateTimeConstraint(self, route, cost_change):
            """This method checks whether or not by inserting a node(customer) we violate the time constraint
                It returns True in case of a violation,False otherwise """
            return route.cost + cost_change > route.t_max -(1e-3)

    def ViolateCapacityConstraint(self, route, customer):
        """This method checks whether or not by inserting a node(customer) we violate the capacity constraint
            It returns True in case of a violation,False otherwise """
        return route.load + customer.demand > route.capacity
#------Area of functions designed to clone(copy) solutions/routes------#
    def CloneSolution(self,solution):
        cloned = Solution()
        for route in solution.routes:
            new_route = self.CloneRoute(route)
            cloned.routes.append(new_route)
        cloned.totalprofit = solution.totalprofit
        cloned.totalcost = solution.totalcost
        return cloned
    def CloneRoute(self,rt):
        new_route = Route(self.depot,self.t_max, self.capacity)
        new_route.sequenceOfNodes =  rt.sequenceOfNodes.copy()
        new_route.cost = rt.cost
        new_route.profit = rt.profit
        new_route.load = rt.load
        return new_route