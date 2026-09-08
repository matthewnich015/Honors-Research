# SCOPE: runs the calculations to determine the amount of ADUs allowed for each combination of variables

import math
import random
import pandas as pd
import geopandas as gpd
import shapely as shapely

# === PRIVATE FUNCTIONS ================================================================================================
index = 1
# checks if an ADU can fit in a parcel. Can only check for one ADU, not multiple, and only checks for detatched
def ADUCheckBasic(buildableArea: shapely.Polygon):
    # check overall square feet
    if buildableArea.area < 190:
        return False, buildableArea
    else:
        # create 2 polygons to test if they fit (square case and long case, general approximation for all cases)
        ADU1 = shapely.Polygon([(0, 0), (13.79, 0), (13.79, 13.79), (0, 13.79)])
        ADU2 = shapely.Polygon([(0, 0), (7, 0), (7, 27.15), (0, 27.15)])
        ADUSizes = [ADU1, ADU2]
        # find centroid, bounding box, and radius in both directions of polygon
        centroid = buildableArea.centroid
        minX, minY, maxX, maxY = buildableArea.bounds
        radiusX = abs(maxX - minX) / 2
        radiusY = abs(maxY - minY) / 2

        # run optimization polygon containment method on both ADU sizes to see if they fit
        fits = False
        for ADU in ADUSizes:
            if fits:
                break
            # set defaults
            vars = {1: centroid.x + random.randrange((-int(radiusX)), (int(radiusX))),
                    2: centroid.y + random.randrange((-int(radiusY)), (int(radiusY))),
                    3: 90} # vars are: posX, posY, rot
            varsLast = vars.copy() # vars are: posX, posY, rot
            score = 0
            scoreLast = 0

            # try 10 times to get it inside the polygon by placing randomly, this will get most cases very quickly
            options = {}
            for i in range(0, 10):
                vars = {1: centroid.x + random.randrange((-int(radiusX)), (int(radiusX))),
                        2: centroid.y + random.randrange((-int(radiusY)), (int(radiusY))),
                        3: 90}  # vars are: posX, posY, rot
                ADUT = shapely.translate(ADU, xoff=vars[1], yoff=vars[2])
                ADUT = shapely.rotate(ADUT, vars[3])
                overlap = buildableArea.intersection(ADUT)
                score = overlap.area
                if score > 189.9:
                    fits = True
                    break
                options[str(i+1)] = (vars[1], vars[2], vars[3], score)

            # if that didn't work, assume it is a harder case and continue with the best 3 of 10
            if not fits:
                bestOptions = [options[str(1)], options[str(2)], options[str(3)]]
                for i in range(4, 11):
                    worstIndex = bestOptions.index(min(bestOptions, key=lambda k: k[3]))
                    if options[str(i)][3] > bestOptions[worstIndex][3]:
                        bestOptions[worstIndex] = options[str(i)]

                # for each of the best 3 of 10, run the optimization function
                for bestOption in bestOptions:
                    if not fits:
                        # set defaults
                        vars[1], vars[2], vars[3] = bestOption[0], bestOption[1], bestOption[2]
                        score = bestOption[3]

                        varsShift = {1: 1, 2: 1, 3: 1}  # vars are: posXDir, posYDir, rotDir
                        scoreMax = 0
                        currentVar = 1
                        beenHereBefore = 0
                        iteration = 1

                        while score < 189.9:
                            varsLast = vars.copy()
                            scoreLast = score

                            # shift variable
                            if currentVar == 3:
                                variableShift = varsShift[currentVar] * 30
                            else:
                                variableShift = varsShift[currentVar] * 30 * (1 - score / 190)
                            vars[currentVar] += variableShift

                            # evaulate new score
                            ADUT = shapely.translate(ADU, xoff=vars[1], yoff=vars[2])
                            ADUT = shapely.rotate(ADUT, vars[3])
                            overlap = buildableArea.intersection(ADUT)
                            score = overlap.area

                            # re-evaluate shift for next time based on results
                            if score - scoreLast > 0:
                                if vars[currentVar] - varsLast[currentVar] > 0:
                                    varsShift[currentVar] = 1 # if the shift helped and was positive, stay positive
                                else:
                                    varsShift[currentVar] = -1 # if the shift helped and was negative, stay negative
                            else:
                                if vars[currentVar] - varsLast[currentVar] > 0:
                                    varsShift[currentVar] = -1 # if the shift didn't help and was positive, change to negative
                                else:
                                    varsShift[currentVar] = 1 # if the shift didnt help and was negative, change to positive

                            # if score is 190, mark as fits
                            if score > 189.9:
                                fits = True
                                break

                            # if score equals max score and max score didnt change, iterate beenHereBefore
                            if score > scoreMax - 1 and score < scoreMax + 1:
                                beenHereBefore += 1
                            # adjust new max score
                            if score > scoreMax:
                                scoreMax = score
                            # if beenHereBefore equals 5 or iteration equals 10000, assume a loop and exit
                            iteration += 1
                            if beenHereBefore == 5 or iteration == 1000:
                                break

                            # change currentVar
                            if currentVar < 3:
                                currentVar += 1
                            else:
                                currentVar = 1
        if fits:
            # buildableArea = buildableArea.difference(ADUT) # cut out for testing
            return True, buildableArea
        else:
            return False, buildableArea

# checks if multiple ADUs can fit in a parcel and returns the number and type that can fit (detatched / attatched)
#def ADUCheckMultiUnit(buildableArea: Polygon, MaxUnits):

# use this to seperate the front and back yard of a parcel
def SplitFrontBackYard(parcel: shapely.Polygon):
    print("Splitting Yard")
    # load data
    root = "../Data/"
    drivewayPolygons = gpd.read_file(root + "Driveway_Polygons/Driveway_Polygons.shp")
    buildingPolygons = gpd.read_file(root + "Building_Polygons/Building_Polygons.shp")
    streetNetworkLines = gpd.read_file(root + "Street_Network/Street_Network.shp")

    # find the bounding box polygon of the parcel and convert to edges
    bbox = parcel.minimum_rotated_rectangle
    coords = list(bbox.exterior.coords)
    edges = [shapely.LineString([coords[i], coords[i+1]]) for i in range(len(coords)-1)]
    bboxE = gpd.GeoDataFrame({"Edge_Type": None, "geometry": edges}, crs="EPSG:2283")

    # find the front of the bbox using the road centerline
    # create a buffer of the bbox and get only the road segments that intersect with that buffer
    buffer = bbox.buffer(100)
    nearbyStreets = gpd.clip(streetNetworkLines, buffer)
    # for each edge in the bbox
    fronts = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:2283")
    if len(nearbyStreets) != 0:
        print("there are streets")
        for idx, row in bboxE.iterrows():
            edge = row.geometry
            edgeCenter = edge.centroid
            # check if the edge is close enough to mark as front yard
            distance = min(edgeCenter.distance(nearbyStreets.geometry))
            if distance < 50:
                print("found a front")
                row = gpd.GeoDataFrame([{"geometry": bboxE.loc[idx, "geometry"]}], crs = fronts.crs)
                fronts = pd.concat([fronts, row], ignore_index=True)
    # if there are more than one front edge or no front edges, use the driveway to determine the correct front edge
    if len(fronts) != 1:
        fronts = fronts.iloc[0:0]
        clipped = gpd.clip(drivewayPolygons, bbox)
        if len(clipped) > 0:
            driveway = shapely.union_all(clipped.geometry)
        else: driveway = None
        # if there is no driveway or nearby streets, choose an edge at random
        if driveway == None or len(nearbyStreets) == 0:
            row = gpd.GeoDataFrame([{"geometry": bboxE.loc[0, "geometry"]}], crs = fronts.crs)
            fronts = pd.concat([fronts, row], ignore_index=True)
        else:
            print("using driveway")
            # find the closest street to the driveway
            nearbyStreets["distance"] = nearbyStreets.geometry.distance(driveway)
            closestStreetSegment = nearbyStreets.loc[nearbyStreets["distance"].idxmin()]
            # find the edge closest to the closest street
            distIdx = (10000, 0)
            for idx, row in bboxE.iterrows():
                edgeCenter = row.geometry.centroid
                distance = edgeCenter.distance(closestStreetSegment.geometry)
                if distance < distIdx[0]:
                    distIdx = (distance, idx)
            print(distIdx)
            row = gpd.GeoDataFrame([{"geometry": bboxE.loc[distIdx[1], "geometry"]}], crs = fronts.crs)
            fronts = pd.concat([fronts, row], ignore_index=True)
    front = fronts.loc[0, "geometry"]

    # find all buildings in the parcel
    buildings = gpd.clip(buildingPolygons, bbox)
    # find the largest building (main house)
    if len(buildings) != 0:
        building = buildings.loc[buildings.geometry.area.idxmax()]
        # find the center point
        buildingCenter = building.geometry.centroid
    # if there are no buildings, the center point will be the parcel centroid
    else:
        buildingCenter = parcel.centroid

    # move the front edge to the center point
    coords = list(front.coords)
    offsetX = buildingCenter.x - coords[0][0]
    offsetY = buildingCenter.y - coords[0][1]
    yardSplit = shapely.affinity.translate(front, offsetX, offsetY)
    # expand the line in both directions
    coords = list(yardSplit.coords)
    direction = (coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
    newCoords = ([(coords[0][0] - direction[0], coords[0][1] - direction[1])] + coords +
                 [(coords[1][0] + direction[0], coords[1][1] + direction[1])])
    yardSplit = shapely.LineString(newCoords)

    # split the bounding box with the line
    split = shapely.ops.split(bbox, yardSplit)
    splitBox = list(split.geoms)
    # mark as front and back yard
    dist1 = splitBox[0].centroid.distance(front)
    dist2 = splitBox[1].centroid.distance(front)
    if dist1 < dist2:
        frontBox = splitBox[0]
        backBox = splitBox[1]
    else:
        frontBox = splitBox[1]
        backBox = splitBox[0]
    # use the split bounding box to split the parcel
    parcelGDF = gpd.GeoDataFrame(geometry=[parcel], crs = fronts.crs)
    frontYardGDF = gpd.clip(parcelGDF, frontBox)
    backYardGDF = gpd.clip(parcelGDF, backBox)
    return pd.Series({"Front_Yard": shapely.union_all(frontYardGDF.geometry), "Back_Yard": shapely.union_all(backYardGDF.geometry)})

# === STEP 0: SETUP ====================================================================================================
def Step0():
    print("STEP 0: Loading Data")
    root = "../Data/"
    # Projected Coordinate System: NAD 1983 StatePlane Virginia North FIPS 4501 (US Feet)
    # Projection: Lambert Conformal Conic
    # WKID: 2283
    parcelPolygons = gpd.read_file(root + "Parcel_Polygons/REA_Property_Polygons.shp")
    zoningPolygons = gpd.read_file(root + "Zoning_Polygons/Zoning_Polygons.shp")
    floodplainPolygons = gpd.read_file(root + "FEMA_Flood_Zone_Polygons/FEMA_Flood_Zone_Polygons.shp")
    historicDistrictPolygons = gpd.read_file(root + "Zoning_Historic_District_Polygons/Zoning_Historic_District_Polygons.shp")
    buildingPolygons = gpd.read_file(root + "Building_Polygons/Building_Polygons.shp")
    drivewayPolygons = gpd.read_file(root + "Driveway_Polygons/Driveway_Polygons.shp")

    print("STEP 0: Removing parcels in non-residential zones, floodplains, or historic districts")
    # remove all parcels that are not residential zoned or are in a floodplain or historic district
    nonResidentialMask = ~zoningPolygons["ZN_DESIG"].str.contains("R-6|R-5|R-8|R-10|R-20|R15-30T|R-10T|R2-7|RA-H-3.2")
    nonResidentialPolygons = zoningPolygons[nonResidentialMask]

    floodplainPolygons = floodplainPolygons[floodplainPolygons.geometry.is_valid]
    mask = floodplainPolygons["FLD_ZONE"].str.contains("A")
    floodplainPolygons = floodplainPolygons[mask]

    merged = gpd.GeoDataFrame(pd.concat([floodplainPolygons, historicDistrictPolygons, nonResidentialPolygons]))
    mask = parcelPolygons.geometry.apply(lambda g: merged.intersects(g).any())
    filteredParcelPolygons = parcelPolygons[~mask]

    # remove all building footprints that aren't in remaining parcels
    print("STEP 0: Removing all building footprints that aren't in remaining parcels")
    buildingPolygons = buildingPolygons[buildingPolygons.geometry.is_valid]
    filteredFootprintPolygons = buildingPolygons.overlay(filteredParcelPolygons, how="intersection")

    # cut building footprint and driveways out of remaining parcels
    print("STEP 0: Removing building footprints and driveways from parcels")
    merged = gpd.GeoDataFrame(pd.concat([filteredFootprintPolygons, drivewayPolygons]))
    parcelStartPolygons = filteredParcelPolygons.overlay(merged, how="difference")

    # add all necessary columns into the geodataframe
    print("STEP 0: Adding columns to parcels to be filled in in steps 1, 2 and 3")
    parcelStartPolygons[["Total_Count", "Detatched_Count", "Attached_Count", "Existing_Count",
        "Walk_Score", "Bike_Score", "Transit_Score", "Near_Transit", "Median_Household_Income", "Median_Age"]] = None

    print("STEP 0: Saving results to file")
    parcelStartPolygons.to_file("../Output/Step0_Parcels.gpkg", driver="GPKG", layer="ParcelStart")
    filteredFootprintPolygons.to_file("../Output/Step0_Building_Footprints.gpkg", driver="GPKG", layer="FilteredFootprints")

# === STEP 1: SETBACKS, LOT COVERAGE, AND FAR ==========================================================================

def Step1():
    print("STEP 1: Loading Data")
    root = "../Data/"
    # Projected Coordinate System: NAD 1983 StatePlane Virginia North FIPS 4501 (US Feet)
    # Projection: Lambert Conformal Conic
    # WKID: 2283
    parcelPolygons = gpd.read_file("../Output/Step0_Parcels.gpkg", driver="GPKG", layer="ParcelStart")
    buildingFootprintPolygons = gpd.read_file("../Output/Step0_BuildingFootprints.gpkg", driver="GPKG", layer="ParcelStart")
    streetNetworkLines = gpd.read_file(root + "Street_Network/Street_Network.shp")



def ADUCheckTest():
    box = gpd.read_file("../box2.gpkg")
    parcels = gpd.read_file("../Output/Test1.gpkg")
    parcels = parcels.overlay(box, how="intersection")
    # === TEST 3 ===
    # results = parcels.geometry.apply(ADUCheckBasic).apply(pd.Series)
    # parcels["Test"] = results[0]
    # parcels = parcels.drop(columns=[col for col in parcels.columns if parcels[col].dtype == "geometry"])
    # parcels = gpd.GeoDataFrame(parcels, geometry=results[1], crs="EPSG:2283")
    # parcels["Test"], parcels.geometry = parcels.geometry.apply(ADUCheckBasic)
    # parcels.to_file("../Output/Test3.gpkg", driver="GPKG", layer="FilteredFootprints")

    # === TEST 4 ===
    results = parcels.geometry.apply(SplitFrontBackYard).apply(pd.Series)
    frontYards = gpd.GeoDataFrame(geometry=results["Front_Yard"], crs=parcels.crs)
    backYards = gpd.GeoDataFrame(geometry=results["Back_Yard"], crs=parcels.crs)
    parcels = pd.concat([frontYards, backYards], ignore_index=True)
    parcels.to_file("../Output/Test4.gpkg", driver="GPKG", layer="FrontBackSplit")