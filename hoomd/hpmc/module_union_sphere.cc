// Copyright (c) 2009-2016 The Regents of the University of Michigan
// This file is part of the HOOMD-blue project, released under the BSD 3-Clause License.

// Include the defined classes that are to be exported to python
#include "IntegratorHPMC.h"
#include "IntegratorHPMCMono.h"
#include "IntegratorHPMCMonoImplicit.h"
#include "ComputeFreeVolume.h"

#include "ShapeSphere.h"
#include "ShapeConvexPolygon.h"
#include "ShapePolyhedron.h"
#include "ShapeConvexPolyhedron.h"
#include "ShapeSpheropolyhedron.h"
#include "ShapeSpheropolygon.h"
#include "ShapeSimplePolygon.h"
#include "ShapeEllipsoid.h"
#include "ShapeFacetedSphere.h"
#include "ShapeSphinx.h"
#include "AnalyzerSDF.h"
#include "ShapeUnion.h"

#include "ExternalField.h"
#include "ExternalFieldWall.h"
#include "ExternalFieldLattice.h"
#include "ExternalFieldComposite.h"

#include "UpdaterExternalFieldWall.h"
#include "UpdaterRemoveDrift.h"
#include "UpdaterMuVT.h"
#include "UpdaterMuVTImplicit.h"

#ifdef ENABLE_CUDA
#include "IntegratorHPMCMonoGPU.h"
#include "IntegratorHPMCMonoImplicitGPU.h"
#include "ComputeFreeVolumeGPU.h"
#endif

// Include boost.python to do the exporting
#include <boost/python.hpp>

using namespace boost::python;
using namespace hpmc;

using namespace hpmc::detail;

namespace hpmc
{

//! Export the base HPMCMono integrators
void export_union_sphere()
    {
    export_IntegratorHPMCMono< ShapeUnion<ShapeSphere> >("IntegratorHPMCMonoSphereUnion");
    export_IntegratorHPMCMonoImplicit< ShapeUnion<ShapeSphere> >("IntegratorHPMCMonoImplicitSphereUnion");
    export_ComputeFreeVolume< ShapeUnion<ShapeSphere> >("ComputeFreeVolumeSphereUnion");
    // export_AnalyzerSDF< ShapeUnion<ShapeSphere> >("AnalyzerSDFSphereUnion");
    export_UpdaterMuVT< ShapeUnion<ShapeSphere> >("UpdaterMuVTSphereUnion");
    export_UpdaterMuVTImplicit< ShapeUnion<ShapeSphere> >("UpdaterMuVTImplicitSphereUnion");

    export_ExternalFieldInterface<ShapeUnion<ShapeSphere> >("ExternalFieldSphereUnion");
    export_LatticeField<ShapeUnion<ShapeSphere> >("ExternalFieldLatticeSphereUnion");
    export_ExternalFieldComposite<ShapeUnion<ShapeSphere> >("ExternalFieldCompositeSphereUnion");
    export_RemoveDriftUpdater<ShapeUnion<ShapeSphere> >("RemoveDriftUpdaterSphereUnion");
    export_ExternalFieldWall<ShapeUnion<ShapeSphere> >("WallSphereUnion");
    export_UpdaterExternalFieldWall<ShapeUnion<ShapeSphere> >("UpdaterExternalFieldWallSphereUnion");

    #ifdef ENABLE_CUDA

    export_IntegratorHPMCMonoGPU< ShapeUnion<ShapeSphere> >("IntegratorHPMCMonoGPUSphereUnion");
    export_IntegratorHPMCMonoImplicitGPU< ShapeUnion<ShapeSphere> >("IntegratorHPMCMonoImplicitGPUSphereUnion");
    export_ComputeFreeVolumeGPU< ShapeUnion<ShapeSphere> >("ComputeFreeVolumeGPUSphereUnion");

    #endif
    }

}