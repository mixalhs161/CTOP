def write_solution_to_file(solution, filename):

    with open(filename, 'w') as f:
        for route in solution.routes:
            # Παράλειπε empty routes (μόνο [depot, depot])
            if len(route.sequenceOfNodes) <= 2:
                continue

            # Sanity check: route ξεκινά και τελειώνει στο depot
            assert route.sequenceOfNodes[0].isDepot, \
                "Route does not start at depot."
            assert route.sequenceOfNodes[-1].isDepot, \
                "Route does not end at depot."

            # Εξαγωγή ids και γραφή σε μία γραμμή
            ids = [node.id for node in route.sequenceOfNodes]
            line = " ".join(str(i) for i in ids)
            f.write(line + "\n")
