import bpy
from .sampling import *

import shapely
from shapely import Polygon, Point, MultiPoint, MultiPolygon, coverage_union_all
from shapely.ops import triangulate
import bmesh

def get_ordered_boundary_vertices(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    boundary_edges = [edge for edge in bm.edges if len(edge.link_faces) < 2]
    if not boundary_edges:
        bm.free()
        return []
    
    # Find an edge to start with
    edge = boundary_edges[0]
    vert = edge.verts[0]
    
    ordered_vertices = [vert]
    current_edge = edge
    boundary_edges.remove(current_edge)
    
    while boundary_edges:
        next_vert = current_edge.other_vert(vert)
        ordered_vertices.append(next_vert)
        vert = next_vert
        
        # Find the next edge
        for edge in boundary_edges:
            if vert in edge.verts:
                current_edge = edge
                boundary_edges.remove(current_edge)
                break

    # Extract coordinates before freeing the BMesh
    retval = [(v.co.x, v.co.y) for v in ordered_vertices]
    bm.free()
    return retval

def obj_to_poly(obj):
    ordered_vertices = get_ordered_boundary_vertices(obj)
    return Polygon(ordered_vertices)

def coverage_ratio(polygon):
    return polygon.area / polygon.envelope.area

def export_poly(poly):
    with open('test.svg', 'w') as f:
        f.write('<svg version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink= "http://www.w3.org/1999/xlink"><g transform="scale(1000 1000)">')
        f.write(p.svg())
        f.write('</g></svg>')

def triangulate_poly_and_points(poly, points, shape_buffer=0.0001):
    pts = points

    r = poly.buffer(shape_buffer)
    for p in list(poly.boundary.coords): pts.append(p)

    triangles = [ t for t in shapely.ops.triangulate(shapely.MultiPoint(pts)) ]

    # triangles = [ t for t in triangles if poly.contains(t) ]
    # triangles = [ t for t in triangles if (poly.intersection(t).area / t.area) > 0.97 ]
    triangles = [ t for t in triangles if r.contains(t) ]
    
    points = {}
    faces = []
    i = 0

    for t in triangles:
        for c in list(t.exterior.coords):
            if c not in points:
                points[c] = i
                i = i + 1

    for t in triangles: faces.append([ points[c] for c in list(t.exterior.coords) ])

    verts = [ None for k in points ]
    for p, i in points.items(): verts[i] = [ p[0], p[1], 0 ]
        
    mesh = bpy.data.meshes.new(name="New Object Mesh")
    mesh.from_pydata(verts, [], faces)
    return mesh
