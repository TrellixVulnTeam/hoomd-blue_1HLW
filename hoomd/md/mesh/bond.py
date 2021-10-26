# Copyright (c) 2009-2021 The Regents of the University of Michigan
# This file is part of the HOOMD-blue project, released under the BSD 3-Clause
# License.

"""Bond potentials."""

from hoomd.md import _md
from hoomd.mesh import Mesh
from hoomd.md.force import Force
from hoomd.data.typeparam import TypeParameter
from hoomd.data.parameterdicts import TypeParameterDict
from hoomd.data.typeconverter import OnlyTypes
import hoomd
import warnings
import copy

validate_mesh = OnlyTypes(Mesh)


class MeshBond(Force):
    """Constructs the bond potential applied to a mesh.

    Note:
        :py:class:`MeshBond` is the base class for all bond potentials applied
        to meshes. Users should not instantiate this class directly.
    """

    def __init__(self, mesh):
        self._mesh = validate_mesh(mesh)

    def _add(self, simulation):
        # if mesh was associated with multiple pair forces and is still
        # attached, we need to deepcopy existing mesh.
        mesh = self._mesh
        if (not self._attached and mesh._attached
                and mesh._simulation != simulation):
            warnings.warn(
                f"{self} object is creating a new equivalent mesh structure."
                f" This is happending since the force is moving to a new "
                f"simulation. To supress the warning explicitly set new mesh.",
                RuntimeWarning)
            self._mesh = copy.deepcopy(mesh)
        # We need to check if the force is added since if it is not then this is
        # being called by a SyncedList object and a disagreement between the
        # simulation and mesh._simulation is an error. If the force is added
        # then the mesh is compatible. We cannot just check the mesh's _added
        # property because _add is also called when the SyncedList is synced.
        elif (not self._added and mesh._added
              and mesh._simulation != simulation):
            raise RuntimeError(
                f"Mesh associated with {self} is associated with "
                f"another simulation.")
        super()._add(simulation)
        # this ideopotent given the above check.
        self._mesh._add(simulation)
        # This is ideopotent, but we need to ensure that if we change
        # neighbor list when not attached we handle correctly.
        self._add_dependency(self._mesh)

    def _attach(self):
        """Create the c++ mirror class."""
        if not self._mesh._added:
            self._mesh._add(self._simulation)
        else:
            if self._simulation != self._mesh._simulation:
                raise RuntimeError("{} object's mesh is used in a "
                                   "different simulation.".format(type(self)))

        if not self.mesh._attached:
            self.mesh._attach()

        if isinstance(self._simulation.device, hoomd.device.CPU):
            cpp_cls = getattr(_md, self._cpp_class_name)
        else:
            cpp_cls = getattr(_md, self._cpp_class_name + "GPU")

        self._cpp_obj = cpp_cls(self._simulation.state._cpp_sys_def,
                                self._mesh._cpp_obj)

        self._apply_param_dict()
        self._apply_typeparam_dict_with_mesh(self._cpp_obj, self.mesh)

    def _apply_typeparam_dict_with_mesh(self, cpp_obj, mesh):
        for typeparam in self._typeparam_dict.values():
            try:
                typeparam._attach_with_mesh(cpp_obj, mesh)
            except ValueError as err:
                raise err.__class__(
                    f"For {type(self)} in TypeParameter {typeparam.name} "
                    f"{str(err)}")

    @property
    def mesh(self):
        """Mesh data structure used to compute the bond potential."""
        return self._mesh

    @mesh.setter
    def mesh(self, value):
        if self._attached:
            raise RuntimeError("mesh cannot be set after scheduling.")
        mesh = validate_mesh(value)
        if self._added:
            if mesh._added and self._simulation != mesh._simulation:
                raise RuntimeError("Mesh and forces must belong to the same "
                                   "simulation or SyncedList.")
            self._mesh._add(self._simulation)
        self._mesh = mesh

    @property
    def _children(self):
        return [self.mesh]


class Harmonic(MeshBond):
    r"""Harmonic bond potential.

    :py:class:`Harmonic` specifies a harmonic potential energy between all
    particles that share an edge within the mesh. For more details see
    :py:class:`hoomd.md.bond.Harmonic`.

    Args:
        mesh (:py:mod:`hoomd.mesh.Mesh`): Mesh data structure constraint.

    Attributes:
        params (TypeParameter[``mesh type``, dict]):
            The parameter of the harmonic bonds for each particle type.
            The dictionary has the following keys:

            * ``k`` (`float`, **required**) - potential constant
              :math:`[\mathrm{energy} \cdot \mathrm{length}^{-2}]`

            * ``r0`` (`float`, **required**) - rest length
              :math:`[\mathrm{length}]`

    Examples::

        harmonic = mesh.bond.Harmonic(mesh)
        harmonic.params['wall'] = dict(k=3.0, r0=2.38)
        harmonic.params['vesicle'] = dict(k=10.0, r0=1.0)
    """
    _cpp_class_name = "PotentialMeshBondHarmonic"

    def __init__(self, mesh):
        params = TypeParameter("params", "types",
                               TypeParameterDict(k=float, r0=float, len_keys=1))
        self._add_typeparam(params)

        super().__init__(mesh)


class FENE(MeshBond):
    r"""FENE bond potential.

    :py:class:`FENE` specifies a FENE potential energy between all
    particles that share an edge within the mesh. For more details see
    :py:class:`hoomd.md.bond.FENE`.

    Args:
        mesh (:py:mod:`hoomd.mesh.Mesh`): Mesh data structure constraint.

    Attributes:
        params (TypeParameter[``mesh type``, dict]):
            The parameter of the FENE potential bonds.
            The dictionary has the following keys:

            * ``k`` (`float`, **required**) - attractive force strength
              :math:`[\mathrm{energy} \cdot \mathrm{length}^{-2}]`

            * ``r0`` (`float`, **required**) - size parameter
              :math:`[\mathrm{length}]`

            * ``epsilon`` (`float`, **required**) - repulsive force strength
              :math:`[\mathrm{energy}]`

            * ``sigma`` (`float`, **required**) - repulsive force interaction
              :math:`[\mathrm{length}]`

    Examples::

        bond_potential = mesh.bond.FENE(mesh)
        bond_potential.params['molecule'] = dict(k=3.0, r0=2.38,
                                                 epsilon=1.0, sigma=1.0)
        bond_potential.params['vesicle'] = dict(k=10.0, r0=1.0,
                                                 epsilon=0.8, sigma=1.2)

    """
    _cpp_class_name = "PotentialMeshBondFENE"

    def __init__(self, mesh):
        params = TypeParameter(
            "params", "types",
            TypeParameterDict(k=float,
                              r0=float,
                              epsilon=float,
                              sigma=float,
                              len_keys=1))
        self._add_typeparam(params)

        super().__init__(mesh)


class Tether(MeshBond):
    r"""Tethering bond potential.

    :py:class:`Tether` specifies a Tethering potential energy between all
    particles that share an edge within the mesh. For more details see
    :py:class:`hoomd.md.bond.Tethering`.

    Args:
        mesh (:py:mod:`hoomd.mesh.Mesh`): Mesh data structure constraint.

    Attributes:
        params (TypeParameter[``mesh type``, dict]):
            The parameter of the Tethering potential bonds.
            The dictionary has the following keys:

            * ``k_b`` (`float`, **required**) - bond stiffness
              :math:`[\mathrm{energy}]`

            * ``l_min`` (`float`, **required**) - minimum bond length
              :math:`[\mathrm{length}]`

            * ``l_c1`` (`float`, **required**) - cutoff distance of repulsive
              part :math:`[\mathrm{length}]`

            * ``l_c0`` (`float`, **required**) - cutoff distance of attractive
              part :math:`[\mathrm{length}]`

            * ``l_max`` (`float`, **required**) - maximum bond length
              :math:`[\mathrm{length}]`

    Examples::

        bond_potential = mesh.bond.Tether(mesh)
        bond_potential.params['tether'] = dict(k_b=10.0, l_min=0.9, l_c1=1.2,
                                               l_c0=1.8, l_max=2.1)
    """
    _cpp_class_name = "PotentialMeshBondTether"

    def __init__(self, mesh):
        params = TypeParameter(
            "params", "types",
            TypeParameterDict(k_b=float,
                              l_min=float,
                              l_c1=float,
                              l_c0=float,
                              l_max=float,
                              len_keys=1))
        self._add_typeparam(params)

        super().__init__(mesh)