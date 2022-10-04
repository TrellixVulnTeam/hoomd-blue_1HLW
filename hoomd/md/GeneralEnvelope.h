// Copyright (c) 2009-2022 The Regents of the University of Michigan.
// Part of HOOMD-blue, released under the BSD 3-Clause License.


#ifndef __GENERAL_ENVELOPE_H__
#define __GENERAL_ENVELOPE_H__

#ifndef __HIPCC__
#include <string>
#endif

#include "hoomd/HOOMDMath.h"

// need to declare these class methods with __device__ qualifiers when building in nvcc
// DEVICE is __host__ __device__ when included in nvcc and blank when included into the host
// compiler
#ifdef __HIPCC__
#define DEVICE __device__
#define HOSTDEVICE __host__ __device__
#else
#define DEVICE
#define HOSTDEVICE
#endif

namespace hoomd
    {
namespace md
    {

/*
  This creates JanusEnvelope, which is used to modulate a pair potential.
*/
template <typename AngleDependence> // thing that we modulate the potential by
class GeneralEnvelope // TODO fix this word
{
public:
    typedef typename AngleDependence::param_type param_type;

    //! Constructor
    DEVICE GeneralEnvelope(
        const Scalar3& _dr,
        const Scalar4& _quat_i,
        const Scalar4& _quat_j,
        const Scalar& _rcutsq,
        const param_type& _params):
        s(_dr, _quat_i, _quat_j, _rcutsq, _params) {}

    //! uses diameter
    DEVICE static bool needsDiameter() { return false; }

    //! Accept the optional diameter values
    /*! \param di Diameter of particle i
      \param dj Diameter of particle j
    */
    DEVICE void setDiameter(Scalar di, Scalar dj) { }

    //! whether pair potential requires charges
    DEVICE static bool needsCharge() { return false; }

    //! Accept the optional charge values
    /*!
      \param qi Charge of particle i
      \param qj Charge of particle j
    */
    DEVICE void setCharge(Scalar qi, Scalar qj) { }

    //! Whether the pair potential needs particle tags.
    DEVICE static bool needsTags() { return false; }

    //! Accept the optional tags
    /*! \param tag_i Tag of particle i
        \param tag_j Tag of particle j
    */
    HOSTDEVICE void setTags(unsigned int tagi, unsigned int tagj) { }


    //! Evaluate the force and energy
    /*
      \param force Output parameter to write the computed force.
      \param isoModulator Output parameter to write the amount of modulation of the isotropic part
      \param torque_i The torque exterted on the i^th particle.
      \param torque_j The torque exterted on the j^th particle.
      \note There is no need to check if rsq < rcutsq in this method. Cutoff tests are performed in PotentialPairJanusSphere.
      \return Always true
    */
    DEVICE bool evaluate(Scalar3& force,
                         Scalar& isoModulator,
                         Scalar3& torque_i,
                         Scalar3& torque_j)
        {
            // common calculations
            Scalar modi = s.Modulatori();
            Scalar modj = s.Modulatorj();
            Scalar modPi = s.ModulatorPrimei();
            Scalar modPj = s.ModulatorPrimej();

            // the overall modulation
            isoModulator = modi*modj;

            // intermediate calculations
            Scalar iPj = modPi*modj/s.magdr;
            Scalar jPi = modPj*modi/s.magdr;
            
            // torque on ith
            torque_i.x = iPj*(s.dr.z*s.ei.y-s.dr.y*s.ei.z);
            torque_i.y = iPj*(s.dr.x*s.ei.z-s.dr.z*s.ei.x);
            torque_i.z = iPj*(s.dr.y*s.ei.x-s.dr.x*s.ei.y);

            // torque on jth - note sign is opposite ith!
            torque_j.x = jPi*(s.dr.y*s.ej.z-s.dr.z*s.ej.y);
            torque_j.y = jPi*(s.dr.z*s.ej.x-s.dr.x*s.ej.z);
            torque_j.z = jPi*(s.dr.x*s.ej.y-s.dr.y*s.ej.x);

            // compute force contribution
            force.x = -(iPj*(-s.ei.x-s.doti*s.dr.x/s.magdr)
                        +jPi*(s.ej.x-s.dotj*s.dr.x/s.magdr));
            force.y = -(iPj*(-s.ei.y-s.doti*s.dr.y/s.magdr)
                        +jPi*(s.ej.y-s.dotj*s.dr.y/s.magdr));
            force.z = -(iPj*(-s.ei.z-s.doti*s.dr.z/s.magdr)
                        +jPi*(s.ej.z-s.dotj*s.dr.z/s.magdr));
            
            return true;
        }

#ifndef _HIPCC_
    //! Get the name of the potential
    static std::string getName()
        {
            return std::string("generalenvelope");
        }
#endif
    
private:
        AngleDependence s;
};

    } // end namespace md
    } // end namespace hoomd
        
#endif // __GENERAL_ENVELOPE_H__