from Parser import *
from dataclasses import dataclass
from typing import List
import random
import copy
import math
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
        self.node = None
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

class InsertMove:
    def __init__(self):
        self.targetRoutePosition = None
        self.targetNodePosition = None
        self.costChange = None
        self.profitChange = None
        self.moveCost = None
        self.node = None


    def Initialize(self):
        self.targetRoutePosition = None
        self.targetNodePosition = None
        self.costChange = 0
        self.profitChange = 0
        self.moveCost = -10**9  # Initialize to a very small number since we are maximizing profit
        self.node = None

class RelocationMove(object):
    def __init__(self):
        self.originRoutePosition = None
        self.targetRoutePosition = None
        self.originNodePosition = None
        self.targetNodePosition = None
        self.costChangeOriginRt = None
        self.costChangeTargetRt = None
        self.profitChangeOriginRt = None
        self.profitChangeTargetRt = None
        self.moveCost = None
        self.costChange = None
        self.profitChange = None


    def Initialize(self):
        self.originRoutePosition = None
        self.targetRoutePosition = None
        self.originNodePosition = None
        self.targetNodePosition = None
        self.costChangeOriginRt = None
        self.costChangeTargetRt = None
        self.profitChangeOriginRt = None
        self.profitChangeTargetRt = None
        self.costChange = None
        self.profitChange = None
        self.moveCost = -10 ** 9

class TwoOptMove(object):
    def __init__(self):
        self.positionOfFirstRoute = None
        self.positionOfSecondRoute = None
        self.positionOfFirstNode = None
        self.positionOfSecondNode = None
        self.costChangeTargetRt = None
        self.profitChangeOriginRt = None
        self.profitChangeTargetRt = None
        self.costChange = None
        self.profitChange = None
        self.moveCost = None

    def Initialize(self):
        self.positionOfFirstRoute = None
        self.positionOfSecondRoute = None
        self.positionOfFirstNode = None
        self.positionOfSecondNode = None
        self.costChangeTargetRt = None
        self.profitChangeOriginRt = None
        self.profitChangeTargetRt = None
        self.costChange = None
        self.profitChange = None
        self.moveCost = -10 ** 9


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
        self.max_iterations = 1200
        self.starting_temperature = 47
        self.final_temperature = 0.01
        self.cooling_rate = 0.995



    def solve(self,enforce_mandatory):

        seeds=[4, 8, 15, 16, 23, 42]
        self.enforce_mandatory = enforce_mandatory
        self.SetRoutedFlagToFalseForAllNodes()
        if self.enforce_mandatory:
            self.MinimumInsertionsMandatory()
            from Alns_mand import run_alns
            improved_solution = run_alns(self.model, self.sol,6000)
            self.sol = improved_solution

            return self.sol
        else:
            self.SetRoutedFlagToFalseForAllNodes()
            self.MinimumInsertionsWithRcl(4)
            self.Ils_Sa()



    def FindBestSwapBetweenRouted_Unrouted(self,smru):
        """
        Exhaustively search for the best swap move only between Unrouted and Routed customers
        """
        for node in self.nodes:
            if not node.isRouted:
                for route_idx in range(0, len(self.sol.routes)):
                    route:Route = self.sol.routes[route_idx]
                    for node_idx in range(1,len(route.sequenceOfNodes)-1):
                        #Get the nodes involved
                        A = route.sequenceOfNodes[node_idx-1]
                        B = route.sequenceOfNodes[node_idx]
                        C = route.sequenceOfNodes[node_idx+1]
                        #calculating cost change
                        costRemoved = self.cost_matrix[A.id][B.id] + self.cost_matrix[B.id][C.id]
                        costAdded = self.cost_matrix[A.id][node.id] + self.cost_matrix[node.id][C.id]
                        cost_change= costAdded - costRemoved
                        #checking for time violation
                        if self.ViolateTimeConstraint(route, cost_change):
                            continue
                        #Checking for load violation
                        if route.load + node.demand - B.demand > route.capacity:
                            continue
                        if self.enforce_mandatory and B.isMandatory:
                            continue
                        #calculating profit change
                        profit_change = node.profit - B.profit
                        move_cost = (self.BIG_NUMBER * profit_change) - cost_change

                        if move_cost > smru.moveCost:
                            smru.originRoutePosition = route_idx
                            smru.originNodePosition = node_idx
                            smru.costChange = cost_change
                            smru.profitChange = profit_change
                            smru.moveCost = move_cost
                            smru.node = node

    def ApplyBestMoveBetweenRouted_Unrouted(self,smru):

        #Unpack the object
        route = self.sol.routes[smru.originRoutePosition]
        node_toremove = route.sequenceOfNodes[smru.originNodePosition]
        node_toadd = smru.node
        route.sequenceOfNodes[smru.originNodePosition] = node_toadd
        route.profit +=  smru.profitChange
        route.cost = route.cost + smru.costChange
        route.load += node_toadd.demand - node_toremove.demand
        node_toremove.isRouted = False
        node_toadd.isRouted = True
        self.sol.totalcost += smru.costChange
        self.sol.totalprofit += smru.profitChange

    def FindBestInsertMove(self, im):
        """
        Exhaustively search for the best insert move.

        Evaluates inserting each UNROUTED customer at every position
        in every route.  Only considers feasible insertions (distance
        budget not exceeded) .
        """
        for node in self.nodes:
            if not node.isRouted:
                for route_idx, route in enumerate(self.sol.routes):
                    for node_idx in range(len(route.sequenceOfNodes) - 1):
                        A = route.sequenceOfNodes[node_idx]
                        B = route.sequenceOfNodes[node_idx + 1]

                        cost_added = self.cost_matrix[A.id][node.id] + self.cost_matrix[node.id][B.id]
                        cost_removed = self.cost_matrix[A.id][B.id]
                        cost_change = cost_added - cost_removed
                        if route.load + node.demand > route.capacity:
                            continue
                        if self.ViolateTimeConstraint(route,cost_change):
                            continue

                        profit_change = node.profit
                        move_cost = (self.BIG_NUMBER * profit_change) - cost_change
                        if move_cost > im.moveCost:
                            im.node = node
                            im.targetRoutePosition = route_idx
                            im.targetNodePosition = node_idx
                            im.costChange = cost_change
                            im.profitChange = profit_change
                            im.moveCost = move_cost


    def ApplyInsertMove(self, im):
        route = self.sol.routes[im.targetRoutePosition]
        route.sequenceOfNodes.insert(im.targetNodePosition + 1, im.node)
        route.cost += im.costChange
        route.profit += im.profitChange
        route.load += im.node.demand
        im.node.isRouted = True
        self.sol.totalcost += im.costChange
        self.sol.totalprofit += im.profitChange

    def FindBestRelocationMove(self, rl):
        for originRouteIndex in range(0, len(self.sol.routes)):
            rt1: Route = self.sol.routes[originRouteIndex]
            for targetRouteIndex in range(0, len(self.sol.routes)):
                rt2: Route = self.sol.routes[targetRouteIndex]
                for originNodeIndex in range(1, len(rt1.sequenceOfNodes) - 1):
                    for targetNodeIndex in range(0, len(rt2.sequenceOfNodes) - 1):

                        if originRouteIndex == targetRouteIndex and (targetNodeIndex == originNodeIndex or targetNodeIndex == originNodeIndex - 1):
                            continue

                        A = rt1.sequenceOfNodes[originNodeIndex - 1]
                        B = rt1.sequenceOfNodes[originNodeIndex]
                        C = rt1.sequenceOfNodes[originNodeIndex + 1]

                        F = rt2.sequenceOfNodes[targetNodeIndex]
                        G = rt2.sequenceOfNodes[targetNodeIndex + 1]

                        cost_change_first_route = self.cost_matrix[A.id][C.id] - self.cost_matrix[A.id][B.id] - self.cost_matrix[B.id][C.id]
                        cost_change_second_route = self.cost_matrix[F.id][B.id] + self.cost_matrix[B.id][G.id] - self.cost_matrix[F.id][G.id]
                        total_cost_change = cost_change_first_route + cost_change_second_route

                        if originRouteIndex == targetRouteIndex:
                            if self.ViolateTimeConstraint(rt1,total_cost_change):
                                continue
                        else:

                            if self.ViolateTimeConstraint(rt2, cost_change_second_route):
                                continue
                            if rt2.load + B.demand > rt2.capacity:
                                continue

                        profitChangeOriginRt = -B.profit
                        profitChangeTargetRt = B.profit
                        profit_change = profitChangeOriginRt + profitChangeTargetRt

                        move_cost = (self.BIG_NUMBER * profit_change) - total_cost_change

                        if move_cost > rl.moveCost:
                            rl.originRoutePosition = originRouteIndex
                            rl.targetRoutePosition = targetRouteIndex
                            rl.originNodePosition = originNodeIndex
                            rl.targetNodePosition = targetNodeIndex
                            rl.costChange = total_cost_change
                            rl.costChangeOriginRt = cost_change_first_route
                            rl.costChangeTargetRt = cost_change_second_route
                            rl.profitChangeOriginRt = profitChangeOriginRt
                            rl.profitChangeTargetRt = profitChangeTargetRt
                            rl.profitChange = profit_change
                            rl.moveCost = move_cost

    def ApplyRelocationMove(self, rl: RelocationMove):


        originRt = self.sol.routes[rl.originRoutePosition]
        targetRt = self.sol.routes[rl.targetRoutePosition]

        B = originRt.sequenceOfNodes[rl.originNodePosition]

        if originRt == targetRt:
            del originRt.sequenceOfNodes[rl.originNodePosition]
            if (rl.originNodePosition < rl.targetNodePosition):
                targetRt.sequenceOfNodes.insert(rl.targetNodePosition, B)
            else:
                targetRt.sequenceOfNodes.insert(rl.targetNodePosition + 1, B)
            originRt.cost += rl.costChange
            originRt.profit += rl.profitChange
        else:
            del originRt.sequenceOfNodes[rl.originNodePosition]
            targetRt.sequenceOfNodes.insert(rl.targetNodePosition + 1, B)
            originRt.cost += rl.costChangeOriginRt
            targetRt.cost += rl.costChangeTargetRt
            originRt.profit += rl.profitChangeOriginRt
            targetRt.profit += rl.profitChangeTargetRt
            originRt.load -= B.demand
            targetRt.load += B.demand

        self.sol.totalcost += rl.costChange
        self.sol.totalprofit += rl.profitChange

    def FindBestTwoOptMove(self, top):
        for rt1Idx in range(len(self.sol.routes)):
            rt1 = self.sol.routes[rt1Idx]
            for rt2Idx in range(rt1Idx, len(self.sol.routes)):
                rt2 = self.sol.routes[rt2Idx]
                for nodeIdx1 in range(len(rt1.sequenceOfNodes) - 1):
                    start2 = nodeIdx1 + 2 if rt1 == rt2 else 0
                    for nodeIdx2 in range(start2, len(rt2.sequenceOfNodes) - 1):

                        A = rt1.sequenceOfNodes[nodeIdx1]
                        B = rt1.sequenceOfNodes[nodeIdx1 + 1]
                        K = rt2.sequenceOfNodes[nodeIdx2]
                        L = rt2.sequenceOfNodes[nodeIdx2 + 1]

                        if rt1 == rt2:
                            if nodeIdx1 == 0 and nodeIdx2 == len(rt1.sequenceOfNodes) - 2:
                                continue
                            costChange = ((self.cost_matrix[A.id][K.id] + self.cost_matrix[B.id][L.id])
                                        - (self.cost_matrix[A.id][B.id] + self.cost_matrix[K.id][L.id]))

                            if rt1.cost + costChange > self.t_max:
                                continue

                        else:
                            if nodeIdx1 == 0 and nodeIdx2 == 0:
                                continue
                            if nodeIdx1 == len(rt1.sequenceOfNodes) - 2 and nodeIdx2 == len(rt2.sequenceOfNodes) - 2:
                                continue
                            if self.CapacityViolatedTwoOpt(rt1, nodeIdx1, rt2, nodeIdx2):
                                continue

                            costChange = ((self.cost_matrix[A.id][L.id] + self.cost_matrix[B.id][K.id])
                                        - (self.cost_matrix[A.id][B.id] + self.cost_matrix[K.id][L.id]))

                            # Check time on both new routes
                            new_cost_rt1 = self.CostAfterTailSwap(rt1, nodeIdx1, rt2, nodeIdx2, is_first=True)
                            new_cost_rt2 = self.CostAfterTailSwap(rt1, nodeIdx1, rt2, nodeIdx2, is_first=False)
                            if new_cost_rt1 > self.t_max or new_cost_rt2 > self.t_max:
                                continue



                        moveCost = -costChange
                        if moveCost > top.moveCost:
                            top.positionOfFirstRoute = rt1Idx
                            top.positionOfSecondRoute = rt2Idx
                            top.positionOfFirstNode = nodeIdx1
                            top.positionOfSecondNode = nodeIdx2
                            top.costChange = costChange
                            top.profitChange = 0
                            top.moveCost = moveCost


    def ApplyTwoOptMove(self, top):
        rt1 = self.sol.routes[top.positionOfFirstRoute]
        rt2 = self.sol.routes[top.positionOfSecondRoute]

        if rt1 == rt2:
            rt1.sequenceOfNodes[top.positionOfFirstNode + 1: top.positionOfSecondNode + 1] = \
                reversed(rt1.sequenceOfNodes[top.positionOfFirstNode + 1: top.positionOfSecondNode + 1])
            rt1.cost += top.costChange
        else:
            tail1 = rt1.sequenceOfNodes[top.positionOfFirstNode + 1:]
            tail2 = rt2.sequenceOfNodes[top.positionOfSecondNode + 1:]
            del rt1.sequenceOfNodes[top.positionOfFirstNode + 1:]
            del rt2.sequenceOfNodes[top.positionOfSecondNode + 1:]
            rt1.sequenceOfNodes.extend(tail2)
            rt2.sequenceOfNodes.extend(tail1)
            self.UpdateRouteCostLoadProfit(rt1)
            self.UpdateRouteCostLoadProfit(rt2)

        self.sol.totalcost += top.costChange


    def CapacityViolatedTwoOpt(self, rt1, nodeIdx1, rt2, nodeIdx2):
        load1_head = sum(rt1.sequenceOfNodes[i].demand for i in range(1, nodeIdx1 + 1))
        load1_tail = rt1.load - load1_head
        load2_head = sum(rt2.sequenceOfNodes[i].demand for i in range(1, nodeIdx2 + 1))
        load2_tail = rt2.load - load2_head
        return (load1_head + load2_tail > self.capacity or
                load2_head + load1_tail > self.capacity)


    def CostAfterTailSwap(self, rt1, idx1, rt2, idx2, is_first):
        if is_first:
            # rt1 head + rt2 tail
            seq = rt1.sequenceOfNodes[:idx1 + 1] + rt2.sequenceOfNodes[idx2 + 1:]
        else:
            # rt2 head + rt1 tail
            seq = rt2.sequenceOfNodes[:idx2 + 1] + rt1.sequenceOfNodes[idx1 + 1:]
        return sum(self.cost_matrix[seq[k].id][seq[k + 1].id] for k in range(len(seq) - 1))


    def UpdateRouteCostLoadProfit(self, rt):
        rt.cost = sum(self.cost_matrix[rt.sequenceOfNodes[i].id][rt.sequenceOfNodes[i + 1].id]
                    for i in range(len(rt.sequenceOfNodes) - 1))
        rt.load = sum(n.demand for n in rt.sequenceOfNodes if not n.isDepot)
        rt.profit = sum(n.profit for n in rt.sequenceOfNodes if not n.isDepot)

    def RebuildRoutedFlags(self):
        self.SetRoutedFlagToFalseForAllNodes()
        for rt in self.sol.routes:
            for n in rt.sequenceOfNodes:
                if not n.isDepot:
                    n.isRouted = True

    def SetRoutedFlagToFalseForAllNodes(self):
       #Mark every node as unrouted
        for node in self.nodes:
            node.isRouted = False

    #-----------NO_MANDATORY INSTANCE AREA-----------#
    def Ils_Sa(self):
        ils_iterations = 0
        current_temperature = self.starting_temperature
        self.LocalSearch()
        local_optimum = self.CloneSolution(self.sol)
        best_solution = local_optimum
        stagnation_counter = 0
        deltas =[]
        while (ils_iterations <= self.max_iterations and current_temperature > self.final_temperature):
            self.Perturb()
            self.LocalSearch()
            delta = self.sol.totalprofit - local_optimum.totalprofit
            if delta < 0:
                deltas.append(abs(delta))
            if self.sol.totalprofit > local_optimum.totalprofit:
                local_optimum = self.CloneSolution(self.sol)
                stagnation_counter = 0
                if self.sol.totalprofit > best_solution.totalprofit:
                    best_solution = local_optimum
            elif math.exp((self.sol.totalprofit - local_optimum.totalprofit)/current_temperature) > random.uniform(0,1):
                local_optimum = self.CloneSolution(self.sol)
                stagnation_counter += 1
            else:
                self.sol = self.CloneSolution(local_optimum)
                self.RebuildRoutedFlags()
                stagnation_counter += 1
            if stagnation_counter >= 50:
                current_temperature = self.starting_temperature * 0.1
                stagnation_counter = 0
            current_temperature = self.UpdateTemperature(current_temperature)
            ils_iterations += 1

            print(f'Iteration {ils_iterations} | profit {self.sol.totalprofit}' )
        self.sol = self.CloneSolution(best_solution)
        print(f'Mean |delta|: {sum(deltas)/len(deltas):.2f}')
        print(f'Max |delta|: {max(deltas)}')
        print(f'Min |delta|: {min(deltas)}')
    def UpdateTemperature(self,current_temperature):
        return current_temperature*self.cooling_rate

    def LocalSearch(self):

        terminal_condition = False
        #Creating MoveType Objects
        top = TwoOptMove()
        rl = RelocationMove()
        im = InsertMove()
        smru = SwapBetweenUnrouted_Routed()

        two_opt_local_optimum = False
        relocation_local_optimum = False
        insertion_local_optimum = False
        swap_local_optimum = False
        while (not terminal_condition):
            while not two_opt_local_optimum:
                top.Initialize()
                self.FindBestTwoOptMove(top)
                if top.costChange < 0:
                    self.ApplyTwoOptMove(top)
                else:
                    two_opt_local_optimum = True
            while not relocation_local_optimum:
                rl.Initialize()
                self.FindBestRelocationMove(rl)
                if rl.costChange < 0:
                    self.ApplyRelocationMove(rl)
                else:
                    relocation_local_optimum = True
            while not insertion_local_optimum:
                im.Initialize()
                self.FindBestInsertMove(im)
                if im.moveCost > 0:

                    self.ApplyInsertMove(im)
                else:
                    insertion_local_optimum = True
            while not swap_local_optimum:
                smru.Initialize()
                self.FindBestSwapBetweenRouted_Unrouted(smru)
                if smru.moveCost > 0:

                    self.ApplyBestMoveBetweenRouted_Unrouted(smru)
                else:
                    swap_local_optimum = True
            terminal_condition = True

        return self.sol


    def Perturb(self):
        self.Node_Removal()
        self.RepairSolutionWithMinimumInsertions()

    def Node_Removal(self):
        candidates = [n
                      for rt in self.sol.routes
                      for n in rt.sequenceOfNodes
                      if n.isRouted and  not n.isDepot
                       ]
        total_nodes_in_solution = len(candidates)

        num_of_nodes_to_remove = random.randint(5,10)
        nodes_to_remove = random.sample(candidates, num_of_nodes_to_remove)
        for node in nodes_to_remove:
            for rt in self.sol.routes:
                if node in rt.sequenceOfNodes:
                    rt.sequenceOfNodes.remove(node)
                    rt.load -= node.demand
                    rt.profit -= node.profit
                    node.isRouted = False
                    self.sol.totalprofit -= node.profit
                    break
        for rt in self.sol.routes:
            rt.cost = sum(self.cost_matrix[rt.sequenceOfNodes[i].id][rt.sequenceOfNodes[i+1].id]
                          for i in range(0,len(rt.sequenceOfNodes)-1))

        self.sol.totalcost = sum(rt.cost for rt in self.sol.routes)

    def RepairSolutionWithMinimumInsertions(self):
        unvisited_nodes = [n for n in self.nodes if not n.isDepot and not n.isRouted]
        while unvisited_nodes:
            best_insertion = CustomerInsertAllPositions()
            self.IdentifyBestCustomerInsertionwithRcl(best_insertion, unvisited_nodes)
            if best_insertion.node is not None:
                self.ApplyBestCustomerInsertion(best_insertion, unvisited_nodes)
            else:
                break
        return self.sol

    def IdentifyBestCustomerInsertion(self,best_insertion,unvisited_nodes):
        for node in unvisited_nodes:
            for route in self.sol.routes:
                for i in range(0, len(route.sequenceOfNodes)-1):
                    A = route.sequenceOfNodes[i]
                    B = route.sequenceOfNodes[i+1]
                    cost_added = self.cost_matrix[A.id][node.id] +self.cost_matrix[node.id][B.id]
                    cost_removed = self.cost_matrix[A.id][B.id]
                    cost_change = cost_added - cost_removed
                    profit_change = node.profit
                    move_cost =(self.BIG_NUMBER * profit_change) - cost_change
                    #Check feasibility
                    if self.ViolateTimeConstraint(route, cost_change):
                        continue
                    if self.ViolateCapacityConstraint(route, node):
                        continue
                    if move_cost > best_insertion.movecost:
                        best_insertion.node         = node
                        best_insertion.route        = route
                        best_insertion.movecost    = move_cost
                        best_insertion.cost_change  = cost_change
                        best_insertion.profit       = profit_change
                        best_insertion.position     = i+1

    def MinimumInsertionsWithRcl(self,seed):
        random.seed(seed)
        self.sol = Solution()
        for _ in range(self.vehicles):
            new_route = Route(self.depot,self.t_max, self.capacity)
            self.sol.routes.append(new_route)
        unvisited_nodes = [n for n in self.nodes if not n.isDepot and not n.isRouted]
        while unvisited_nodes:
            best_insertion = CustomerInsertAllPositions()
            self.IdentifyBestCustomerInsertionwithRcl(best_insertion, unvisited_nodes)
            if best_insertion.node is not None:
                self.ApplyBestCustomerInsertion(best_insertion, unvisited_nodes)
            else:
                break
        print(self.sol.totalprofit)
        return self.sol

    def IdentifyBestCustomerInsertionwithRcl(self, best_insertion,unvisited_nodes):
        rcl = []
        for node in unvisited_nodes:
            for route in self.sol.routes:
                for i in range(0, len(route.sequenceOfNodes)-1):
                    A = route.sequenceOfNodes[i]
                    B = route.sequenceOfNodes[i+1]
                    cost_added = self.cost_matrix[A.id][node.id] +self.cost_matrix[node.id][B.id]
                    cost_removed = self.cost_matrix[A.id][B.id]
                    cost_change = cost_added - cost_removed
                    profit_change = node.profit
                    move_cost =(self.BIG_NUMBER * profit_change) - cost_change
                    #Check feasibility
                    if self.ViolateTimeConstraint(route, cost_change):
                        continue
                    if self.ViolateCapacityConstraint(route, node):
                        continue
                    #Rcl insertion
                    if len(rcl) < self.rcl_size:
                        new_tup = (node, route, move_cost,cost_change, profit_change, i+1)
                        rcl.append(new_tup)
                        rcl.sort(key=lambda x:x[2],reverse=True)
                    else:
                        if move_cost > rcl[-1][2]:
                            rcl.pop()
                            new_tup = (node, route, move_cost, cost_change, profit_change, i+1)
                            rcl.append(new_tup)
                            rcl.sort(key=lambda x:x[2], reverse=True)
        if len(rcl) == 0:
            return None
        else:
            chosen = random.choice(rcl)
            best_insertion.node     = chosen[0]
            best_insertion.route        = chosen[1]
            best_insertion.movecost    = chosen[2]
            best_insertion.cost_change  = chosen[3]
            best_insertion.profit       = chosen[4]
            best_insertion.position     = chosen[5]



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
            if best_insertion.node is not None:
                self.ApplyBestCustomerInsertion(best_insertion, unvisited_customers)
            else:
                break
        print(self.sol.totalprofit)
        return self.sol

    def IdentifyBestCustomerInsertionMandatory(self,best_insertion, unvisited_nodes):
        for node in unvisited_nodes:
            for route in self.sol.routes:
                for i in range(0, len(route.sequenceOfNodes)-1):
                    A = route.sequenceOfNodes[i]
                    B = route.sequenceOfNodes[i+1]
                    cost_added = self.cost_matrix[A.id][node.id] +self.cost_matrix[node.id][B.id]
                    cost_removed = self.cost_matrix[A.id][B.id]
                    cost_change = cost_added - cost_removed
                    profit_change = node.profit
                    r_idx = self.sol.routes.index(route)
                    if node.isMandatory:
                        move_cost = (self.BIG_NUMBER * profit_change) - cost_change \
                        + self.mandatory_penalties * self.bonus[node.id][r_idx]
                    else:
                        move_cost = (self.BIG_NUMBER * profit_change) - cost_change
                    #Check feasibility
                    if self.ViolateTimeConstraint(route, cost_change):
                        continue
                    if self.ViolateCapacityConstraint(route, node):
                        continue
                    if move_cost > best_insertion.movecost:
                        best_insertion.node     = node
                        best_insertion.route        = route
                        best_insertion.movecost     = move_cost
                        best_insertion.cost_change  = cost_change
                        best_insertion.profit       = profit_change
                        best_insertion.position     = i+1


    def ApplyBestCustomerInsertion(self,best_insertion,unvisited_nodes):
        #Unpacking the object
        node = best_insertion.node
        unvisited_nodes.remove(node)
        route = best_insertion.route
        position = best_insertion.position
        route.sequenceOfNodes.insert(position, node)
        route.load += node.demand
        route.profit += node.profit
        route.cost += best_insertion.cost_change
        node.isRouted = True
        self.sol.totalcost += best_insertion.cost_change
        self.sol.totalprofit += node.profit
        if self.enforce_mandatory:
            for n in unvisited_nodes:
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