import bpy
from .sampling import *

import shapely
from shapely import Polygon, LinearRing, Point, MultiPoint, MultiPolygon, coverage_union_all
from shapely.ops import triangulate
import bmesh

def get_ordered_boundary_edges(obj):
    if isinstance(obj, bmesh.types.BMesh):
        bm = obj.copy()
    else:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

    # Find boundary edges (edges with only one linked face)
    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) < 2]

    if not boundary_edges:
        return []

    # Function to find a loop starting from a given edge
    def find_loop(start_edge):
        loop = []
        visited_edges = set()
        stack = [start_edge]
        while stack:
            edge = stack.pop()
            if edge not in visited_edges:
                visited_edges.add(edge)
                loop.append(edge)
                linked_edges = [e for vert in edge.verts for e in vert.link_edges if e in boundary_edges and e not in visited_edges]
                stack.extend(linked_edges)
        return loop

    # Find all boundary loops
    boundary_loops = []
    while boundary_edges:
        edge = boundary_edges.pop()
        loop = find_loop(edge)
        for e in loop:
            if e in boundary_edges:
                boundary_edges.remove(e)
        boundary_loops.append(loop)

    # Order the vertices of each loop
    ordered_boundary_loops = []
    for loop in boundary_loops:
        ordered_vertices = []
        edge = loop[0]
        vert = edge.verts[0]
        ordered_vertices.append(vert)
        current_edge = edge
        loop.remove(current_edge)

        while loop:
            next_vert = current_edge.other_vert(vert)
            ordered_vertices.append(next_vert)
            vert = next_vert
            for edge in loop:
                if vert in edge.verts:
                    current_edge = edge
                    loop.remove(current_edge)
                    break

        ordered_boundary_loops.append([(v.co.x, v.co.y) for v in ordered_vertices])  # 2D coordinates (x, y)

    bm.free()
    return ordered_boundary_loops

def obj_to_poly(obj):
    boundary_loops = get_ordered_boundary_edges(obj)
    if not boundary_loops: return None

    # Determine the outer boundary and potential holes
    # Assumption: The largest loop is the outer boundary, and others are holes
    outer_boundary = max(boundary_loops, key=lambda loop: LinearRing(loop).length)
    holes = [loop for loop in boundary_loops if loop != outer_boundary]

    # Create the Shapely Polygon
    polygon = Polygon(outer_boundary, holes)
    return polygon

def export_poly(poly):
    with open('test.svg', 'w') as f:
        f.write('<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink= "http://www.w3.org/1999/xlink"><g transform="scale(1000 1000)">')
        f.write(p.svg())
        f.write('</g></svg>')

def triangulate_poly_and_points(poly, points, shape_buffer=0.001):
    pts = points

    minx, miny, maxx, maxy = poly.bounds
    l = max([maxx - minx, maxy - miny])
    print(l, shape_buffer * l)
    
    r = poly.buffer(shape_buffer * l)
    
    for p in list(poly.exterior.coords): pts.append(p)
    for p in poly.interiors: pts.extend(p.coords)

    
    triangles = [ t for t in shapely.ops.triangulate(shapely.MultiPoint(pts)) ]
    triangles = [ shapely.intersection(poly, t) for t in triangles ]
    
    points = {}
    faces = []
    i = 0
    
    for t in [t for t in triangles if t.geom_type in [ "MultiPolygon", "GeometryCollection" ]]:
        for t in [ t for t in list(t.geoms) if t.geom_type == "Polygon"]:
            triangles.append(t)

    triangles = [t for t in triangles if t.geom_type == "Polygon" ]
            
    for t in triangles:
        for c in list(t.exterior.coords):
            if c not in points:
                points[c] = i
                i = i + 1

    for t in triangles:
        faces.append([ points[c] for c in list(t.exterior.coords) ])
        
    verts = [ None for k in points ]
    for p, i in points.items(): verts[i] = [ p[0], p[1], 0 ]
        
    mesh = bpy.data.meshes.new(name="New Object Mesh")
    mesh.from_pydata(verts, [], faces)
    return mesh
