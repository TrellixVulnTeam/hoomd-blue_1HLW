// Copyright (c) 2009-2021 The Regents of the University of Michigan
// This file is part of the HOOMD-blue project, released under the BSD 3-Clause License.

#include "hoomd/MeshGroupData.cuh"
#include "hoomd/HOOMDMath.h"
#include "hoomd/Index1D.h"
#include "hoomd/ParticleData.cuh"

/*! \file HelfrichMeshForceComputeGPU.cuh
    \brief Declares GPU kernel code for calculating the helfrich forces. Used by
   HelfrichMeshForceComputeGPU.
*/

#ifndef __HELFRICHMESHFORCECOMPUTE_CUH__
#define __HELFRICHMESHFORCECOMPUTE_CUH__

namespace hoomd
    {
namespace md
    {
namespace kernel
    {
//! Kernel driver that computes the sigmas for HelfrichMeshForceComputeGPU
hipError_t gpu_compute_helfrich_sigma(Scalar4* d_sigma,
                                      const unsigned int N,
                                      const Scalar4* d_pos,
                                      const unsigned int* d_tag,
                                      const BoxDim& box,
                                      const unsigned int maxTag,
                                      const group_storage<4>* blist,
                                      const Index2D blist_idx,
                                      const unsigned int* n_bonds_list,
                                      int block_size);


//! Kernel driver that computes the forces for HelfrichMeshForceComputeGPU
hipError_t gpu_compute_helfrich_force(Scalar4* d_force,
                                      Scalar* d_virial,
                                      const size_t virial_pitch,
                                      const unsigned int N,
                                      const Scalar4* d_pos,
                                      const unsigned int* d_tag,
                                      const BoxDim& box,
                                      const unsigned int maxTag,
                                      const Scalar4* d_sigma,
                                      const group_storage<4>* blist,
                                      const Index2D blist_idx,
                                      const unsigned int* n_bonds_list,
                                      Scalar* d_params,
                                      const unsigned int n_bond_type,
                                      int block_size,
                                      unsigned int* d_flags);
    } // end namespace kernel
    } // end namespace md
    } // end namespace hoomd

#endif
