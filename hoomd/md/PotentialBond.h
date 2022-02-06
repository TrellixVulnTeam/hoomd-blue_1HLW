// Copyright (c) 2009-2022 The Regents of the University of Michigan.
// Part of HOOMD-blue, released under the BSD 3-Clause License.

#include "hoomd/ForceCompute.h"
#include "hoomd/GPUArray.h"
#include "hoomd/MeshDefinition.h"
#include <float.h>
#include <memory>

#include <vector>

/*! \file PotentialBond.h
    \brief Declares PotentialBond
*/

#ifdef __HIPCC__
#error This header cannot be compiled by nvcc
#endif

#include <pybind11/pybind11.h>

#ifndef __POTENTIALBOND_H__
#define __POTENTIALBOND_H__

namespace hoomd
    {
namespace md
    {
/*! Bond potential with evaluator support

    \ingroup computes
*/
template<class evaluator, class Bonds> class PotentialBond : public ForceCompute
    {
    public:
    //! Param type from evaluator
    typedef typename evaluator::param_type param_type;

    //! Constructs the compute
    PotentialBond(std::shared_ptr<SystemDefinition> sysdef);

    //! Constructs the compute with external Bond data
    PotentialBond(std::shared_ptr<SystemDefinition> sysdef,
                  std::shared_ptr<MeshDefinition> meshdef);

    //! Destructor
    virtual ~PotentialBond();

    /// Set the parameters
    virtual void setParams(unsigned int type, const param_type& param);
    virtual void setParamsPython(std::string type, pybind11::dict param);

    /// Get the parameters
    pybind11::dict getParams(std::string type);

    /// Validate bond type
    virtual void validateType(unsigned int type, std::string action);

#ifdef ENABLE_MPI
    //! Get ghost particle fields requested by this pair potential
    virtual CommFlags getRequestedCommFlags(uint64_t timestep);
#endif

    protected:
    GPUArray<param_type> m_params;      //!< Bond parameters per type
    std::shared_ptr<Bonds> m_bond_data; //!< Bond data to use in computing bonds
    std::string m_prof_name;            //!< Cached profiler name

    //! Actually compute the forces
    virtual void computeForces(uint64_t timestep);

    virtual Scalar energyDiff(unsigned int idx_a,
                              unsigned int idx_b,
                              unsigned int idx_c,
                              unsigned int idx_d,
                              unsigned int type_id);
    };

template<class evaluator, class Bonds>
PotentialBond<evaluator, Bonds>::PotentialBond(std::shared_ptr<SystemDefinition> sysdef)
    : ForceCompute(sysdef)
    {
    m_exec_conf->msg->notice(5) << "Constructing PotentialBond<" << evaluator::getName() << ">"
                                << std::endl;
    assert(m_pdata);

    // access the bond data for later use
    m_bond_data = m_sysdef->getBondData();
    m_prof_name = std::string("Bond ") + evaluator::getName();

    // allocate the parameters
    GPUArray<param_type> params(m_bond_data->getNTypes(), m_exec_conf);
    m_params.swap(params);
    }

template<class evaluator, class Bonds>
PotentialBond<evaluator, Bonds>::PotentialBond(std::shared_ptr<SystemDefinition> sysdef,
                                               std::shared_ptr<MeshDefinition> meshdef)
    : ForceCompute(sysdef)
    {
    m_exec_conf->msg->notice(5) << "Constructing PotentialMeshBond<" << evaluator::getName() << ">"
                                << std::endl;
    assert(m_pdata);

    // access the bond data for later use
    m_bond_data = meshdef->getMeshBondData();
    m_prof_name = std::string("MeshBond ") + evaluator::getName();

    // allocate the parameters
    GPUArray<param_type> params(m_bond_data->getNTypes(), m_exec_conf);
    m_params.swap(params);
    }

template<class evaluator, class Bonds> PotentialBond<evaluator, Bonds>::~PotentialBond()
    {
    m_exec_conf->msg->notice(5) << "Destroying PotentialBond<" << evaluator::getName() << ">"
                                << std::endl;
    }

/*! \param type Type of the bond to set parameters for
    \param param Parameter to set

    Sets the parameters for the potential of a particular bond type
*/
template<class evaluator, class Bonds>
void PotentialBond<evaluator, Bonds>::validateType(unsigned int type, std::string action)
    {
    // make sure the type is valid
    if (type >= m_bond_data->getNTypes())
        {
        std::string err = "Invalid bond type specified.";
        err += "Error " + action + " in PotentialBond";
        throw std::runtime_error(err);
        }
    }

template<class evaluator, class Bonds>
void PotentialBond<evaluator, Bonds>::setParams(unsigned int type, const param_type& param)
    {
    // make sure the type is valid
    validateType(type, "setting params");
    ArrayHandle<param_type> h_params(m_params, access_location::host, access_mode::readwrite);
    h_params.data[type] = param;
    }

/*! \param types Type of the bond to set parameters for using string
    \param param Parameter to set

    Sets the parameters for the potential of a particular bond type
*/
template<class evaluator, class Bonds>
void PotentialBond<evaluator, Bonds>::setParamsPython(std::string type, pybind11::dict param)
    {
    auto itype = m_bond_data->getTypeByName(type);
    auto struct_param = param_type(param);
    setParams(itype, struct_param);
    }

/*! \param types Type of the bond to set parameters for using string
    \param param Parameter to set

    Sets the parameters for the potential of a particular bond type
*/
template<class evaluator, class Bonds>
pybind11::dict PotentialBond<evaluator, Bonds>::getParams(std::string type)
    {
    auto itype = m_bond_data->getTypeByName(type);
    validateType(itype, "getting params");
    ArrayHandle<param_type> h_params(m_params, access_location::host, access_mode::read);
    return h_params.data[itype].asDict();
    }

/*! Actually perform the force computation
    \param timestep Current time step
 */
template<class evaluator, class Bonds>
void PotentialBond<evaluator, Bonds>::computeForces(uint64_t timestep)
    {
    if (m_prof)
        m_prof->push(m_prof_name);

    assert(m_pdata);

    // access the particle data arrays
    ArrayHandle<Scalar4> h_pos(m_pdata->getPositions(), access_location::host, access_mode::read);
    ArrayHandle<unsigned int> h_rtag(m_pdata->getRTags(), access_location::host, access_mode::read);
    ArrayHandle<Scalar> h_diameter(m_pdata->getDiameters(),
                                   access_location::host,
                                   access_mode::read);
    ArrayHandle<Scalar> h_charge(m_pdata->getCharges(), access_location::host, access_mode::read);

    ArrayHandle<Scalar4> h_force(m_force, access_location::host, access_mode::readwrite);
    ArrayHandle<Scalar> h_virial(m_virial, access_location::host, access_mode::readwrite);

    // access the parameters
    ArrayHandle<param_type> h_params(m_params, access_location::host, access_mode::read);

    // there are enough other checks on the input data: but it doesn't hurt to be safe
    assert(h_force.data);
    assert(h_virial.data);
    assert(h_pos.data);
    assert(h_diameter.data);
    assert(h_charge.data);

    // Zero data for force calculation
    memset((void*)h_force.data, 0, sizeof(Scalar4) * m_force.getNumElements());
    memset((void*)h_virial.data, 0, sizeof(Scalar) * m_virial.getNumElements());

    // we are using the minimum image of the global box here
    // to ensure that ghosts are always correctly wrapped (even if a bond exceeds half the domain
    // length)
    const BoxDim& box = m_pdata->getGlobalBox();

    PDataFlags flags = this->m_pdata->getFlags();
    bool compute_virial = flags[pdata_flag::pressure_tensor];

    Scalar bond_virial[6];
    for (unsigned int i = 0; i < 6; i++)
        bond_virial[i] = Scalar(0.0);

    ArrayHandle<typename Bonds::members_t> h_bonds(m_bond_data->getMembersArray(),
                                                   access_location::host,
                                                   access_mode::read);
    ArrayHandle<typeval_t> h_typeval(m_bond_data->getTypeValArray(),
                                     access_location::host,
                                     access_mode::read);

    unsigned int max_local = m_pdata->getN() + m_pdata->getNGhosts();

    // for each of the bonds
    const unsigned int size = (unsigned int)m_bond_data->getN();

    for (unsigned int i = 0; i < size; i++)
        {
        // lookup the tag of each of the particles participating in the bond
        const typename Bonds::members_t& bond = h_bonds.data[i];
        assert(bond.tag[0] < m_pdata->getMaximumTag() + 1);
        assert(bond.tag[1] < m_pdata->getMaximumTag() + 1);

        // transform a and b into indices into the particle data arrays
        // (MEM TRANSFER: 4 integers)
        unsigned int idx_a = h_rtag.data[bond.tag[0]];
        unsigned int idx_b = h_rtag.data[bond.tag[1]];

        // throw an error if this bond is incomplete
        if (idx_a >= max_local || idx_b >= max_local)
            {
            std::ostringstream stream;
            stream << "Error: bond " << bond.tag[0] << " " << bond.tag[1] << " is incomplete.";
            throw std::runtime_error(stream.str());
            }

        // calculate d\vec{r}
        // (MEM TRANSFER: 6 Scalars / FLOPS: 3)
        Scalar3 posa = make_scalar3(h_pos.data[idx_a].x, h_pos.data[idx_a].y, h_pos.data[idx_a].z);
        Scalar3 posb = make_scalar3(h_pos.data[idx_b].x, h_pos.data[idx_b].y, h_pos.data[idx_b].z);

        Scalar3 dx = posb - posa;

        // access diameter (if needed)
        Scalar diameter_a = Scalar(0.0);
        Scalar diameter_b = Scalar(0.0);
        if (evaluator::needsDiameter())
            {
            diameter_a = h_diameter.data[idx_a];
            diameter_b = h_diameter.data[idx_b];
            }

        // access charge (if needed)
        Scalar charge_a = Scalar(0.0);
        Scalar charge_b = Scalar(0.0);
        if (evaluator::needsCharge())
            {
            charge_a = h_charge.data[idx_a];
            charge_b = h_charge.data[idx_b];
            }

        // if the vector crosses the box, pull it back
        dx = box.minImage(dx);

        // calculate r_ab squared
        Scalar rsq = dot(dx, dx);

        // compute the force and potential energy
        Scalar force_divr = Scalar(0.0);
        Scalar bond_eng = Scalar(0.0);
        evaluator eval(rsq, h_params.data[h_typeval.data[i].type]);
        if (evaluator::needsDiameter())
            eval.setDiameter(diameter_a, diameter_b);
        if (evaluator::needsCharge())
            eval.setCharge(charge_a, charge_b);

        bool evaluated = eval.evalForceAndEnergy(force_divr, bond_eng);

        // Bond energy must be halved
        bond_eng *= Scalar(0.5);

        if (evaluated)
            {
            // calculate virial
            if (compute_virial)
                {
                Scalar force_div2r = Scalar(1.0 / 2.0) * force_divr;
                bond_virial[0] = dx.x * dx.x * force_div2r; // xx
                bond_virial[1] = dx.x * dx.y * force_div2r; // xy
                bond_virial[2] = dx.x * dx.z * force_div2r; // xz
                bond_virial[3] = dx.y * dx.y * force_div2r; // yy
                bond_virial[4] = dx.y * dx.z * force_div2r; // yz
                bond_virial[5] = dx.z * dx.z * force_div2r; // zz
                }

            // add the force to the particles (only for non-ghost particles)
            if (idx_b < m_pdata->getN())
                {
                h_force.data[idx_b].x += force_divr * dx.x;
                h_force.data[idx_b].y += force_divr * dx.y;
                h_force.data[idx_b].z += force_divr * dx.z;
                h_force.data[idx_b].w += bond_eng;
                if (compute_virial)
                    for (unsigned int i = 0; i < 6; i++)
                        h_virial.data[i * m_virial_pitch + idx_b] += bond_virial[i];
                }

            if (idx_a < m_pdata->getN())
                {
                h_force.data[idx_a].x -= force_divr * dx.x;
                h_force.data[idx_a].y -= force_divr * dx.y;
                h_force.data[idx_a].z -= force_divr * dx.z;
                h_force.data[idx_a].w += bond_eng;
                if (compute_virial)
                    for (unsigned int i = 0; i < 6; i++)
                        h_virial.data[i * m_virial_pitch + idx_a] += bond_virial[i];
                }
            }
        else
            {
            this->m_exec_conf->msg->error()
                << "bond." << evaluator::getName() << ": bond out of bounds " << bond.tag[0] << " "
                << bond.tag[1] << " " << rsq << std::endl
                << std::endl;
            throw std::runtime_error("Error in bond calculation");
            }
        }

    if (m_prof)
        m_prof->pop();
    }

template<class evaluator, class Bonds>
Scalar PotentialBond<evaluator, Bonds>::energyDiff(unsigned int idx_a,
                                                   unsigned int idx_b,
                                                   unsigned int idx_c,
                                                   unsigned int idx_d,
                                                   unsigned int type_id)
    {
    ArrayHandle<Scalar4> h_pos(m_pdata->getPositions(), access_location::host, access_mode::read);
    ArrayHandle<Scalar> h_diameter(m_pdata->getDiameters(),
                                   access_location::host,
                                   access_mode::read);
    ArrayHandle<Scalar> h_charge(m_pdata->getCharges(), access_location::host, access_mode::read);

    // access the parameters
    ArrayHandle<param_type> h_params(m_params, access_location::host, access_mode::read);

    const BoxDim& box = m_pdata->getGlobalBox();

    // access diameter (if needed)
    Scalar diameter_a = Scalar(0.0);
    Scalar diameter_b = Scalar(0.0);
    Scalar diameter_c = Scalar(0.0);
    Scalar diameter_d = Scalar(0.0);
    if (evaluator::needsDiameter())
        {
        diameter_a = h_diameter.data[idx_a];
        diameter_b = h_diameter.data[idx_b];
        diameter_c = h_diameter.data[idx_c];
        diameter_d = h_diameter.data[idx_d];
        }

    // access charge (if needed)
    Scalar charge_a = Scalar(0.0);
    Scalar charge_b = Scalar(0.0);
    Scalar charge_c = Scalar(0.0);
    Scalar charge_d = Scalar(0.0);
    if (evaluator::needsCharge())
        {
        charge_a = h_charge.data[idx_a];
        charge_b = h_charge.data[idx_b];
        charge_c = h_charge.data[idx_c];
        charge_d = h_charge.data[idx_d];
        }

    Scalar3 posa = make_scalar3(h_pos.data[idx_a].x, h_pos.data[idx_a].y, h_pos.data[idx_a].z);
    Scalar3 posb = make_scalar3(h_pos.data[idx_b].x, h_pos.data[idx_b].y, h_pos.data[idx_b].z);
    Scalar3 posc = make_scalar3(h_pos.data[idx_c].x, h_pos.data[idx_c].y, h_pos.data[idx_c].z);
    Scalar3 posd = make_scalar3(h_pos.data[idx_d].x, h_pos.data[idx_d].y, h_pos.data[idx_d].z);

    Scalar3 xab = posb - posa;

    Scalar3 xcd = posd - posc;

    xab = box.minImage(xab);
    xcd = box.minImage(xcd);

    // calculate r_ab squared
    Scalar rsqab = dot(xab, xab);
    Scalar rsqcd = dot(xcd, xcd);

    // compute the force and potential energy
    Scalar force_divr = Scalar(0.0);
    Scalar bond_eng1 = Scalar(0.0);
    Scalar bond_eng2 = Scalar(0.0);
    evaluator eval1(rsqab, h_params.data[type_id]);
    evaluator eval2(rsqcd, h_params.data[type_id]);
    if (evaluator::needsDiameter())
        {
        eval1.setDiameter(diameter_a, diameter_b);
        eval2.setDiameter(diameter_c, diameter_d);
        }
    if (evaluator::needsCharge())
        {
        eval1.setCharge(charge_a, charge_b);
        eval2.setCharge(charge_c, charge_d);
        }

    eval1.evalForceAndEnergy(force_divr, bond_eng1);
    bool evaluated = eval2.evalForceAndEnergy(force_divr, bond_eng2);

    if (evaluated)
        return (bond_eng2 - bond_eng1);
    else
        return DBL_MAX;
    }

#ifdef ENABLE_MPI
/*! \param timestep Current time step
 */
template<class evaluator, class Bonds>
CommFlags PotentialBond<evaluator, Bonds>::getRequestedCommFlags(uint64_t timestep)
    {
    CommFlags flags = CommFlags(0);

    flags[comm_flag::tag] = 1;

    if (evaluator::needsCharge())
        flags[comm_flag::charge] = 1;

    if (evaluator::needsDiameter())
        flags[comm_flag::diameter] = 1;

    flags |= ForceCompute::getRequestedCommFlags(timestep);

    return flags;
    }
#endif

namespace detail
    {
//! Exports the PotentialBond class to python
/*! \param name Name of the class in the exported python module
    \tparam T class type to export. \b Must be an instantiated PotentialBOnd class template.
*/
template<class T> void export_PotentialBond(pybind11::module& m, const std::string& name)
    {
    pybind11::class_<T, ForceCompute, std::shared_ptr<T>>(m, name.c_str())
        .def(pybind11::init<std::shared_ptr<SystemDefinition>>())
        .def("setParams", &T::setParamsPython)
        .def("getParams", &T::getParams);
    }

//! Exports the PotentialMeshBond class to python
/*! \param name Name of the class in the exported python module
    \tparam T class type to export. \b Must be an instantiated PotentialBOnd class template.
*/
template<class T> void export_PotentialMeshBond(pybind11::module& m, const std::string& name)
    {
    pybind11::class_<T, ForceCompute, std::shared_ptr<T>>(m, name.c_str())
        .def(pybind11::init<std::shared_ptr<SystemDefinition>, std::shared_ptr<MeshDefinition>>())
        .def("setParams", &T::setParamsPython)
        .def("getParams", &T::getParams);
    }

    } // end namespace detail
    } // end namespace md
    } // end namespace hoomd

#endif
