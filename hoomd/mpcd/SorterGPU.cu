// Copyright (c) 2009-2018 The Regents of the University of Michigan
// This file is part of the HOOMD-blue project, released under the BSD 3-Clause License.

// Maintainer: mphoward

/*!
 * \file mpcd/SorterGPU.cu
 * \brief Defines GPU functions and kernels used by mpcd::SorterGPU
 */

#include "CellListGPU.cuh"

#include "hoomd/extern/cub/cub/device/device_select.cuh"

namespace mpcd
{
namespace gpu
{
namespace kernel
{
//! Kernel to apply sorted particle order
/*!
 * \param d_pos_alt Alternate array of particle positions (output)
 * \param d_vel_alt Alternate array of particle velocities (output)
 * \param d_tag_alt Alternate array of particle tags (output)
 * \param d_pos Particle positions
 * \param d_vel Particle velocities
 * \param d_tag Particle tags
 * \param d_order Mapping of new particle index onto old particle index
 * \param N Number of particles
 *
 * \b Implementation
 * Using one thread per particle, particle data is reordered from the old arrays
 * into the new arrays. This coalesces writes but fragments reads.
 */
__global__ void sort_apply(Scalar4 *d_pos_alt,
                           Scalar4 *d_vel_alt,
                           unsigned int *d_tag_alt,
                           const Scalar4 *d_pos,
                           const Scalar4 *d_vel,
                           const unsigned int *d_tag,
                           const unsigned int *d_order,
                           const unsigned int N)
    {
    // one thread per particle
    const unsigned int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= N)
        return;

    const unsigned int old_idx = d_order[idx];
    d_pos_alt[idx] = d_pos[old_idx];
    d_vel_alt[idx] = d_vel[old_idx];
    d_tag_alt[idx] = d_tag[old_idx];
    }

//! Kernel to set the empty-cell-entry sentinel
/*!
 * \param d_cell_list Cell list to fill in
 * \param d_cell_np Number of particles per cell
 * \param cli Two-dimensional cell-list indexer
 * \param sentinel Value to fill into empty cell-list entries
 * \param N_cli Number of total entries (filled and empty) in the cell list
 *
 * \b Implementation
 * Using one thread per cell-list entry, the 1D kernel index is mapped onto
 * the 2D entry in the cell list. If the current entry is not filled, the entry
 * is filled with the value of \a sentinel. Typically, \a sentinel should be
 * larger than the number of MPCD particles in the system. (A good value would be
 * 0xffffffff). The cell list can subsequently be compacted by mpcd::gpu::sort_cell_compact.
 */
__global__ void sort_set_sentinel(unsigned int *d_cell_list,
                                  const unsigned int *d_cell_np,
                                  const Index2D cli,
                                  const unsigned int sentinel,
                                  const unsigned int N_cli)
    {
    // one thread per cell-list entry
    const unsigned int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= N_cli)
        return;

    // convert the entry 1D index into a 2D index
    const unsigned int cell = idx / cli.getW();
    const unsigned int offset = idx - (cell * cli.getW());

    // if the offset lies outside the number of particles in the cell, fill it with sentinel
    const unsigned int np = d_cell_np[cell];
    if (offset >= np)
        d_cell_list[idx] = sentinel;
    }

//! Kernel to generate the reverse particle mapping
/*!
 * \param d_rorder Map of old particle indexes onto new particle indexes (output)
 * \param d_order Map of new particle indexes onto old particle indexes
 * \param N Number of particles
 *
 * \b Implementation
 * Using one thread per particle, the map generated by mpcd::gpu::sort_cell_compact
 * is read and reversed so that new particle indexes can be looked up from old
 * particle indexes.
 */
__global__ void sort_gen_reverse(unsigned int *d_rorder,
                                 const unsigned int *d_order,
                                 const unsigned int N)
    {
    // one thread per particle
    const unsigned int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= N)
        return;

    // inverse map the ordering
    // d_order maps the new index (idx) onto the old index (pid), so we need to flip this around
    const unsigned int pid = d_order[idx];
    d_rorder[pid] = idx;
    }

} // end namespace kernel

/*!
 * \param d_pos_alt Alternate array of particle positions (output)
 * \param d_vel_alt Alternate array of particle velocities (output)
 * \param d_tag_alt Alternate array of particle tags (output)
 * \param d_pos Particle positions
 * \param d_vel Particle velocities
 * \param d_tag Particle tags
 * \param d_order Mapping of new particle index onto old particle index
 * \param N Number of particles
 * \param block_size Number of threads per block
 *
 * \returns cudaSuccess on completion
 *
 * \sa mpcd::gpu::kernel::sort_apply
 */
cudaError_t sort_apply(Scalar4 *d_pos_alt,
                       Scalar4 *d_vel_alt,
                       unsigned int *d_tag_alt,
                       const Scalar4 *d_pos,
                       const Scalar4 *d_vel,
                       const unsigned int *d_tag,
                       const unsigned int *d_order,
                       const unsigned int N,
                       const unsigned int block_size)
    {
    if (N == 0) return cudaSuccess;

    static unsigned int max_block_size = UINT_MAX;
    if (max_block_size == UINT_MAX)
        {
        cudaFuncAttributes attr;
        cudaFuncGetAttributes(&attr, (const void*)mpcd::gpu::kernel::sort_apply);
        max_block_size = attr.maxThreadsPerBlock;
        }

    unsigned int run_block_size = min(block_size, max_block_size);
    dim3 grid(N / run_block_size + 1);
    mpcd::gpu::kernel::sort_apply<<<grid, run_block_size>>>(d_pos_alt,
                                                            d_vel_alt,
                                                            d_tag_alt,
                                                            d_pos,
                                                            d_vel,
                                                            d_tag,
                                                            d_order,
                                                            N);

    return cudaSuccess;
    }

/*!
 * \param d_cell_list Cell list to fill in
 * \param d_cell_np Number of particles per cell
 * \param cli Two-dimensional cell-list indexer
 * \param sentinel Value to fill into empty cell-list entries
 * \param N_cli Number of total entries (filled and empty) in the cell list
 * \param block_size Number of threads per block
 *
 * \returns cudaSuccess on completion
 *
 * \sa mpcd::gpu::kernel::sort_set_sentinel
 */
cudaError_t sort_set_sentinel(unsigned int *d_cell_list,
                              const unsigned int *d_cell_np,
                              const Index2D& cli,
                              const unsigned int sentinel,
                              const unsigned int block_size)
    {
    static unsigned int max_block_size = UINT_MAX;
    if (max_block_size == UINT_MAX)
        {
        cudaFuncAttributes attr;
        cudaFuncGetAttributes(&attr, (const void*)mpcd::gpu::kernel::sort_set_sentinel);
        max_block_size = attr.maxThreadsPerBlock;
        }

    const unsigned int N_cli = cli.getNumElements();

    unsigned int run_block_size = min(block_size, max_block_size);
    dim3 grid(N_cli / run_block_size + 1);
    mpcd::gpu::kernel::sort_set_sentinel<<<grid, run_block_size>>>(d_cell_list,
                                                                   d_cell_np,
                                                                   cli,
                                                                   sentinel,
                                                                   N_cli);

    return cudaSuccess;
    }

//! Less-than comparison functor for cell-list compaction
struct LessThan
    {
    //! Constructor
    /*!
     * \param compare_ Value to compare less than
     */
    __host__ __device__ __forceinline__
    LessThan(unsigned int compare_)
        : compare(compare_) {}

    //! Less than comparison functor
    /*!
     * \param val
     * \returns True if \a val is less than \a compare
     */
    __host__ __device__ __forceinline__
    bool operator()(const unsigned int& val) const
        {
        return (val < compare);
        }

    unsigned int compare; //!< Value to compare less-than to
    };


/*!
 * \param d_order Compacted MPCD particle indexes in cell-list order (output)
 * \param d_num_select Number of particles in the compaction (output)
 * \param d_tmp_storage Temporary storage for CUB (output)
 * \param tmp_storage_btyes Number of bytes in \a d_tmp_storage (input/output)
 * \param d_cell_list Cell list array to compact
 * \param num_items Number of items in the cell list
 * \param N_mpcd Number of MPCD particles
 *
 * \returns cudaSuccess on completion
 *
 * \b Implementation
 * cub::DeviceSelect::If is used to efficiently compact the MPCD cell list to
 * a stream containing only MPCD particle indexes. First, a sentinel is set to
 * fill in empty entries (mpcd::gpu::sort_set_sentinel). Then, the LessThan functor
 * is used to compare all entries in the cell list, and return only those with
 * indexes less than \a N_mpcd.
 *
 * \b Usage
 * Because this function relies on CUB, it must be called \b twice in order to
 * take effect. On the first call, \a d_tmp_storage should be a NULL pointer.
 * The necessary temporary storage will be sized and stored in \a tmp_storage_bytes.
 * The caller must then allocate the required storage into \a d_tmp_storage,
 * and call this method again. After the second call, the compacted cell list
 * will be stored in \a d_order. \a d_num_select should store a value equal to
 * \a N_mpcd. In debug mode, this value can optionally be copied to the host
 * and checked. However, this involves an unnecessary copy operation, and so is
 * not typically recommended.
 */
cudaError_t sort_cell_compact(unsigned int *d_order,
                              unsigned int *d_num_select,
                              void *d_tmp_storage,
                              size_t& tmp_storage_bytes,
                              const unsigned int *d_cell_list,
                              const unsigned int num_items,
                              const unsigned int N_mpcd)
    {
    LessThan selector(N_mpcd);
    cub::DeviceSelect::If(d_tmp_storage, tmp_storage_bytes, d_cell_list, d_order, d_num_select, num_items, selector);

    return cudaSuccess;
    }

/*!
 * \param d_rorder Map of old particle indexes onto new particle indexes (output)
 * \param d_order Map of new particle indexes onto old particle indexes
 * \param N Number of particles
 *
 * \returns cudaSuccess on completion
 *
 * \sa mpcd::gpu::kernel::sort_gen_reverse
 */
cudaError_t sort_gen_reverse(unsigned int *d_rorder,
                             const unsigned int *d_order,
                             const unsigned int N,
                             const unsigned int block_size)
    {
    if (N == 0) return cudaSuccess;

    static unsigned int max_block_size = UINT_MAX;
    if (max_block_size == UINT_MAX)
        {
        cudaFuncAttributes attr;
        cudaFuncGetAttributes(&attr, (const void*)mpcd::gpu::kernel::sort_gen_reverse);
        max_block_size = attr.maxThreadsPerBlock;
        }

    unsigned int run_block_size = min(block_size, max_block_size);
    dim3 grid(N / run_block_size + 1);
    mpcd::gpu::kernel::sort_gen_reverse<<<grid, run_block_size>>>(d_rorder, d_order, N);

    return cudaSuccess;
    }
} // end namespace gpu
} // end namespace mpcd
