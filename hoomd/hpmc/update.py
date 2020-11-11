# Copyright (c) 2009-2019 The Regents of the University of Michigan
# This file is part of the HOOMD-blue project, released under the BSD 3-Clause License.
R""" HPMC updaters.

Defines new ensembles and updaters to HPMC specifc data structures

"""

from . import _hpmc
from . import integrate
from hoomd import _hoomd
from hoomd.logging import log
from hoomd.update import _updater
from hoomd.data.parameterdicts import ParameterDict
import hoomd.data.typeconverter
from hoomd.operation import Updater
import hoomd
from hoomd.custom import Action


class boxmc(_updater):
    R""" Apply box updates to sample isobaric and related ensembles.

    Args:

        mc (:py:mod:`hoomd.hpmc.integrate`): HPMC integrator object for system on which to apply box updates
        betaP (:py:class:`float` or :py:mod:`hoomd.variant`): :math:`\frac{p}{k_{\mathrm{B}}T}`. (units of inverse area in 2D or
                                                    inverse volume in 3D) Apply your chosen reduced pressure convention
                                                    externally.
        seed (int): random number seed for MC box changes

    One or more Monte Carlo move types are applied to evolve the simulation box. By default, no moves are applied.
    Activate desired move types using the following methods with a non-zero weight:

    - :py:meth:`aspect` - box aspect ratio moves
    - :py:meth:`length` - change box lengths independently
    - :py:meth:`shear` - shear the box
    - :py:meth:`volume` - scale the box lengths uniformly
    - :py:meth:`ln_volume` - scale the box lengths uniformly with logarithmic increments

    Pressure inputs to update.boxmc are defined as :math:`\beta P`. Conversions from a specific definition of reduced
    pressure :math:`P^*` are left for the user to perform.

    Note:
        All *delta* and *weight* values for all move types default to 0.

    Example::

        mc = hpmc.integrate.sphere(seed=415236, d=0.3)
        boxMC = hpmc.update.boxmc(mc, betaP=1.0, seed=9876)
        boxMC.set_betap(2.0)
        boxMC.ln_volume(delta=0.01, weight=2.0)
        boxMC.length(delta=(0.1,0.1,0.1), weight=4.0)
        run(30) # perform approximately 10 volume moves and 20 length moves

    """

    def __init__(self, mc, betaP, seed):
        # initialize base class
        _updater.__init__(self);

        # Updater gets called at every timestep. Whether to perform a move is determined independently
        # according to frequency parameter.
        period = 1

        if not isinstance(mc, integrate.HPMCIntegrator):
            hoomd.context.current.device.cpp_msg.warning("update.boxmc: Must have a handle to an HPMC integrator.\n");
            return;

        self.betaP = hoomd.variant._setup_variant_input(betaP);

        self.seed = int(seed)

        # create the c++ mirror class
        self.cpp_updater = _hpmc.UpdaterBoxMC(hoomd.context.current.system_definition,
                                               mc.cpp_integrator,
                                               self.betaP.cpp_variant,
                                               1,
                                               self.seed,
                                               );
        self.setupUpdater(period);

        self.volume_delta = 0.0;
        self.volume_weight = 0.0;
        self.ln_volume_delta = 0.0;
        self.ln_volume_weight = 0.0;
        self.length_delta = [0.0, 0.0, 0.0];
        self.length_weight = 0.0;
        self.shear_delta = [0.0, 0.0, 0.0];
        self.shear_weight = 0.0;
        self.shear_reduce = 0.0;
        self.aspect_delta = 0.0;
        self.aspect_weight = 0.0;

        self.metadata_fields = ['betaP',
                                 'seed',
                                 'volume_delta',
                                 'volume_weight',
                                 'ln_volume_delta',
                                 'ln_volume_weight',
                                 'length_delta',
                                 'length_weight',
                                 'shear_delta',
                                 'shear_weight',
                                 'shear_reduce',
                                 'aspect_delta',
                                 'aspect_weight']

    def set_betap(self, betaP):
        R""" Update the pressure set point for Metropolis Monte Carlo volume updates.

        Args:
            betaP (float) or (:py:mod:`hoomd.variant`): :math:`\frac{p}{k_{\mathrm{B}}T}`. (units of inverse area in 2D or
                inverse volume in 3D) Apply your chosen reduced pressure convention
                externally.
        """
        self.betaP = hoomd.variant._setup_variant_input(betaP)
        self.cpp_updater.setP(self.betaP.cpp_variant)

    def volume(self, delta=None, weight=None):
        R""" Enable/disable isobaric volume move and set parameters.

        Args:
            delta (float): maximum change of the box area (2D) or volume (3D).
            weight (float): relative weight of this box move type relative to other box move types. 0 disables this move type.

        Sample the isobaric distribution of box volumes by rescaling the box.

        Note:
            When an argument is None, the value is left unchanged from its current state.

        Example::

            box_update.volume(delta=0.01)
            box_update.volume(delta=0.01, weight=2)
            box_update.volume(delta=0.01, weight=0.15)

        Returns:
            A :py:class:`dict` with the current values of *delta* and *weight*.

        """
        self.check_initialization();

        if weight is not None:
            self.volume_weight = float(weight)

        if delta is not None:
            self.volume_delta = float(delta)

        self.cpp_updater.volume(self.volume_delta, self.volume_weight);
        return {'delta': self.volume_delta, 'weight': self.volume_weight};

    def ln_volume(self, delta=None, weight=None):
        R""" Enable/disable isobaric volume move and set parameters.

        Args:
            delta (float): maximum change of **ln(V)** (where V is box area (2D) or volume (3D)).
            weight (float): relative weight of this box move type relative to other box move types. 0 disables this move type.

        Sample the isobaric distribution of box volumes by rescaling the box.

        Note:
            When an argument is None, the value is left unchanged from its current state.

        Example::

            box_update.ln_volume(delta=0.001)
            box_update.ln_volume(delta=0.001, weight=2)
            box_update.ln_volume(delta=0.001, weight=0.15)

        Returns:
            A :py:class:`dict` with the current values of *delta* and *weight*.

        """
        self.check_initialization();

        if weight is not None:
            self.ln_volume_weight = float(weight)

        if delta is not None:
            self.ln_volume_delta = float(delta)

        self.cpp_updater.ln_volume(self.ln_volume_delta, self.ln_volume_weight);
        return {'delta': self.ln_volume_delta, 'weight': self.ln_volume_weight};

    def length(self, delta=None, weight=None):
        R""" Enable/disable isobaric box dimension move and set parameters.

        Args:
            delta (:py:class:`float` or :py:class:`tuple`): maximum change of the box thickness for each pair of parallel planes
                                               connected by the corresponding box edges. I.e. maximum change of
                                               HOOMD-blue box parameters Lx, Ly, Lz. A single float *x* is equivalent to
                                               (*x*, *x*, *x*).
            weight (float): relative weight of this box move type relative to other box move types. 0 disables this
                            move type.

        Sample the isobaric distribution of box dimensions by rescaling the plane-to-plane distance of box faces,
        Lx, Ly, Lz.

        Note:
            When an argument is None, the value is left unchanged from its current state.

        Example::

            box_update.length(delta=(0.01, 0.01, 0.0)) # 2D box changes
            box_update.length(delta=(0.01, 0.01, 0.01), weight=2)
            box_update.length(delta=0.01, weight=2)
            box_update.length(delta=(0.10, 0.01, 0.01), weight=0.15) # sample Lx more aggressively

        Returns:
            A :py:class:`dict` with the current values of *delta* and *weight*.

        """
        self.check_initialization();

        if weight is not None:
            self.length_weight = float(weight)

        if delta is not None:
            if isinstance(delta, float) or isinstance(delta, int):
                self.length_delta = [float(delta)] * 3
            else:
                self.length_delta = [ float(d) for d in delta ]

        self.cpp_updater.length(   self.length_delta[0], self.length_delta[1],
                                        self.length_delta[2], self.length_weight);
        return {'delta': self.length_delta, 'weight': self.length_weight};

    def shear(self,  delta=None, weight=None, reduce=None):
        R""" Enable/disable box shear moves and set parameters.

        Args:
            delta (tuple): maximum change of the box tilt factor xy, xz, yz.
            reduce (float): Maximum number of lattice vectors of shear to allow before applying lattice reduction.
                    Shear of +/- 0.5 cannot be lattice reduced, so set to a value < 0.5 to disable (default 0)
                    Note that due to precision errors, lattice reduction may introduce small overlaps which can be
                    resolved, but which temporarily break detailed balance.
            weight (float): relative weight of this box move type relative to other box move types. 0 disables this
                            move type.

        Sample the distribution of box shear by adjusting the HOOMD-blue tilt factor parameters xy, xz, and yz.

        Note:
            When an argument is None, the value is left unchanged from its current state.

        Example::

            box_update.shear(delta=(0.01, 0.00, 0.0)) # 2D box changes
            box_update.shear(delta=(0.01, 0.01, 0.01), weight=2)
            box_update.shear(delta=(0.10, 0.01, 0.01), weight=0.15) # sample xy more aggressively

        Returns:
            A :py:class:`dict` with the current values of *delta*, *weight*, and *reduce*.

        """
        self.check_initialization();

        if weight is not None:
            self.shear_weight = float(weight)

        if reduce is not None:
            self.shear_reduce = float(reduce)

        if delta is not None:
            if isinstance(delta, float) or isinstance(delta, int):
                self.shear_delta = [float(delta)] * 3
            else:
                self.shear_delta = [ float(d) for d in delta ]

        self.cpp_updater.shear(    self.shear_delta[0], self.shear_delta[1],
                                        self.shear_delta[2], self.shear_reduce,
                                        self.shear_weight);
        return {'delta': self.shear_delta, 'weight': self.shear_weight, 'reduce': self.shear_reduce}

    def aspect(self, delta=None, weight=None):
        R""" Enable/disable aspect ratio move and set parameters.

        Args:
            delta (float): maximum relative change of aspect ratio
            weight (float): relative weight of this box move type relative to other box move types. 0 disables this
                            move type.

        Rescale aspect ratio along a randomly chosen dimension.

        Note:
            When an argument is None, the value is left unchanged from its current state.

        Example::

            box_update.aspect(delta=0.01)
            box_update.aspect(delta=0.01, weight=2)
            box_update.aspect(delta=0.01, weight=0.15)

        Returns:
            A :py:class:`dict` with the current values of *delta*, and *weight*.

        """
        self.check_initialization();

        if weight is not None:
            self.aspect_weight = float(weight)

        if delta is not None:
            self.aspect_delta = float(delta)

        self.cpp_updater.aspect(self.aspect_delta, self.aspect_weight);
        return {'delta': self.aspect_delta, 'weight': self.aspect_weight}

    def get_volume_acceptance(self):
        R""" Get the average acceptance ratio for volume changing moves.

        Returns:
            The average volume change acceptance for the last run

        Example::

            mc = hpmc.integrate.shape(..);
            mc.shape_param[name].set(....);
            box_update = hpmc.update.boxmc(mc, betaP=10, seed=1)
            run(100)
            v_accept = box_update.get_volume_acceptance()

        """
        counters = self.cpp_updater.getCounters(1);
        return counters.getVolumeAcceptance();

    def get_ln_volume_acceptance(self):
        R""" Get the average acceptance ratio for log(V) changing moves.

        Returns:
            The average volume change acceptance for the last run

        Example::

            mc = hpmc.integrate.shape(..);
            mc.shape_param[name].set(....);
            box_update = hpmc.update.boxmc(mc, betaP=10, seed=1)
            run(100)
            v_accept = box_update.get_ln_volume_acceptance()

        """
        counters = self.cpp_updater.getCounters(1);
        return counters.getLogVolumeAcceptance();

    def get_shear_acceptance(self):
        R"""  Get the average acceptance ratio for shear changing moves.

        Returns:
           The average shear change acceptance for the last run

        Example::

            mc = hpmc.integrate.shape(..);
            mc.shape_param[name].set(....);
            box_update = hpmc.update.boxmc(mc, betaP=10, seed=1)
            run(100)
            s_accept = box_update.get_shear_acceptance()

        """
        counters = self.cpp_updater.getCounters(1);
        return counters.getShearAcceptance();
        counters = self.cpp_updater.getCounters(1);
        return counters.getShearAcceptance();

    def get_aspect_acceptance(self):
        R"""  Get the average acceptance ratio for aspect changing moves.

        Returns:
            The average aspect change acceptance for the last run

        Example::

            mc = hpmc.integrate.shape(..);
            mc_shape_param[name].set(....);
            box_update = hpmc.update.boxmc(mc, betaP=10, seed=1)
            run(100)
            a_accept = box_update.get_aspect_acceptance()

        """
        counters = self.cpp_updater.getCounters(1);
        return counters.getAspectAcceptance();
        counters = self.cpp_updater.getCounters(1);
        return counters.getAspectAcceptance();

    def enable(self):
        R""" Enables the updater.

        Example::

            box_updater.set_params(isotropic=True)
            run(1e5)
            box_updater.disable()
            update.box_resize(dLy = 10)
            box_updater.enable()
            run(1e5)

        See updater base class documentation for more information
        """
        self.cpp_updater.computeAspectRatios();
        _updater.enable(self);


class wall(_updater):
    R""" Apply wall updates with a user-provided python callback.

    Args:
        mc (:py:mod:`hoomd.hpmc.integrate`): MC integrator.
        walls (:py:class:`hoomd.hpmc.field.wall`): the wall class instance to be updated
        py_updater (`callable`): the python callback that performs the update moves. This must be a python method that is a function of the timestep of the simulation.
               It must actually update the :py:class:`hoomd.hpmc.field.wall`) managed object.
        move_probability (float): the probability with which an update move is attempted
        seed (int): the seed of the pseudo-random number generator that determines whether or not an update move is attempted
        period (int): the number of timesteps between update move attempt attempts
               Every *period* steps, a walls update move is tried with probability *move_probability*. This update move is provided by the *py_updater* callback.
               Then, update.wall only accepts an update move provided by the python callback if it maintains confinement conditions associated with all walls. Otherwise,
               it reverts back to a non-updated copy of the walls.

    Once initialized, the update provides the following log quantities that can be logged via ``hoomd.analyze.log``:

    * **hpmc_wall_acceptance_ratio** - the acceptance ratio for wall update moves

    Example::

        mc = hpmc.integrate.sphere(seed = 415236);
        ext_wall = hpmc.compute.wall(mc);
        ext_wall.add_sphere_wall(radius = 1.0, origin = [0, 0, 0], inside = True);
        def perturb(timestep):
          r = np.sqrt(ext_wall.get_sphere_wall_param(index = 0, param = "rsq"));
          ext_wall.set_sphere_wall(index = 0, radius = 1.5*r, origin = [0, 0, 0], inside = True);
        wall_updater = hpmc.update.wall(mc, ext_wall, perturb, move_probability = 0.5, seed = 27, period = 50);
        log = analyze.log(quantities=['hpmc_wall_acceptance_ratio'], period=100, filename='log.dat', overwrite=True);

    Example::

        mc = hpmc.integrate.sphere(seed = 415236);
        ext_wall = hpmc.compute.wall(mc);
        ext_wall.add_sphere_wall(radius = 1.0, origin = [0, 0, 0], inside = True);
        def perturb(timestep):
          r = np.sqrt(ext_wall.get_sphere_wall_param(index = 0, param = "rsq"));
          ext_wall.set_sphere_wall(index = 0, radius = 1.5*r, origin = [0, 0, 0], inside = True);
        wall_updater = hpmc.update.wall(mc, ext_wall, perturb, move_probability = 0.5, seed = 27, period = 50);

    """
    def __init__(self, mc, walls, py_updater, move_probability, seed, period=1):

        # initialize base class
        _updater.__init__(self);

        cls = None;
        if isinstance(mc, integrate.sphere):
            cls = _hpmc.UpdaterExternalFieldWallSphere;
        elif isinstance(mc, integrate.convex_polyhedron):
            cls = _hpmc.UpdaterExternalFieldWallConvexPolyhedron;
        elif isinstance(mc, integrate.convex_spheropolyhedron):
            cls = _hpmc.UpdaterExternalFieldWallSpheropolyhedron;
        else:
            hoomd.context.current.device.cpp_msg.error("update.wall: Unsupported integrator.\n");
            raise RuntimeError("Error initializing update.wall");

        self.cpp_updater = cls(hoomd.context.current.system_definition, mc.cpp_integrator, walls.cpp_compute, py_updater, move_probability, seed);
        self.setupUpdater(period);

    def get_accepted_count(self, mode=0):
        R""" Get the number of accepted wall update moves.

        Args:
            mode (int): specify the type of count to return. If mode!=0, return absolute quantities. If mode=0, return quantities relative to the start of the run.
                        DEFAULTS to 0.

        Returns:
           the number of accepted wall update moves

        Example::

            mc = hpmc.integrate.sphere(seed = 415236);
            ext_wall = hpmc.compute.wall(mc);
            ext_wall.add_sphere_wall(radius = 1.0, origin = [0, 0, 0], inside = True);
            def perturb(timestep):
              r = np.sqrt(ext_wall.get_sphere_wall_param(index = 0, param = "rsq"));
              ext_wall.set_sphere_wall(index = 0, radius = 1.5*r, origin = [0, 0, 0], inside = True);
            wall_updater = hpmc.update.wall(mc, ext_wall, perturb, move_probability = 0.5, seed = 27, period = 50);
            run(100);
            acc_count = wall_updater.get_accepted_count(mode = 0);
        """
        return self.cpp_updater.getAcceptedCount(mode);

    def get_total_count(self, mode=0):
        R""" Get the number of attempted wall update moves.

        Args:
            mode (int): specify the type of count to return. If mode!=0, return absolute quantities. If mode=0, return quantities relative to the start of the run.
                        DEFAULTS to 0.

        Returns:
           the number of attempted wall update moves

        Example::

            mc = hpmc.integrate.sphere(seed = 415236);
            ext_wall = hpmc.compute.wall(mc);
            ext_wall.add_sphere_wall(radius = 1.0, origin = [0, 0, 0], inside = True);
            def perturb(timestep):
              r = np.sqrt(ext_wall.get_sphere_wall_param(index = 0, param = "rsq"));
              ext_wall.set_sphere_wall(index = 0, radius = 1.5*r, origin = [0, 0, 0], inside = True);
            wall_updater = hpmc.update.wall(mc, ext_wall, perturb, move_probability = 0.5, seed = 27, period = 50);
            run(100);
            tot_count = wall_updater.get_total_count(mode = 0);

        """
        return self.cpp_updater.getTotalCount(mode);


class muvt(_updater):
    R""" Insert and remove particles in the muVT ensemble.

    Args:
        mc (:py:mod:`hoomd.hpmc.integrate`): MC integrator.
        seed (int): The seed of the pseudo-random number generator (Needs to be the same across partitions of the same Gibbs ensemble)
        period (int): Number of timesteps between histogram evaluations.
        transfer_types (list): List of type names that are being transferred from/to the reservoir or between boxes (if *None*, all types)
        ngibbs (int): The number of partitions to use in Gibbs ensemble simulations (if == 1, perform grand canonical muVT)

    The muVT (or grand-canonical) ensemble simulates a system at constant fugacity.

    Gibbs ensemble simulations are also supported, where particles and volume are swapped between two or more
    boxes.  Every box correspond to one MPI partition, and can therefore run on multiple ranks.
    See ``hoomd.comm`` and the --nrank command line option for how to split a MPI task into partitions.

    Note:
        Multiple Gibbs ensembles are also supported in a single parallel job, with the ngibbs option
        to update.muvt(), where the number of partitions can be a multiple of ngibbs.

    Example::

        mc = hpmc.integrate.sphere(seed=415236)
        update.muvt(mc=mc, period)

    """
    def __init__(self, mc, seed, period=1, transfer_types=None,ngibbs=1):

        if not isinstance(mc, integrate.HPMCIntegrator):
            hoomd.context.current.device.cpp_msg.warning("update.muvt: Must have a handle to an HPMC integrator.\n");
            return;

        self.mc = mc

        # initialize base class
        _updater.__init__(self);

        if ngibbs > 1:
            self.gibbs = True;
        else:
            self.gibbs = False;

        # get a list of types from the particle data
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # by default, transfer all types
        if transfer_types is None:
            transfer_types = type_list

        cls = None;

        if isinstance(mc, integrate.sphere):
            cls = _hpmc.UpdaterMuVTSphere;
        elif isinstance(mc, integrate.convex_polygon):
            cls = _hpmc.UpdaterMuVTConvexPolygon;
        elif isinstance(mc, integrate.simple_polygon):
            cls = _hpmc.UpdaterMuVTSimplePolygon;
        elif isinstance(mc, integrate.convex_polyhedron):
            cls = _hpmc.UpdaterMuVTConvexPolyhedron;
        elif isinstance(mc, integrate.convex_spheropolyhedron):
            cls = _hpmc.UpdaterMuVTSpheropolyhedron;
        elif isinstance(mc, integrate.ellipsoid):
            cls = _hpmc.UpdaterMuVTEllipsoid;
        elif isinstance(mc, integrate.convex_spheropolygon):
            cls =_hpmc.UpdaterMuVTSpheropolygon;
        elif isinstance(mc, integrate.faceted_sphere):
            cls =_hpmc.UpdaterMuVTFacetedEllipsoid;
        elif isinstance(mc, integrate.sphere_union):
            cls = _hpmc.UpdaterMuVTSphereUnion;
        elif isinstance(mc, integrate.convex_spheropolyhedron_union):
            cls = _hpmc.UpdaterMuVTConvexPolyhedronUnion;
        elif isinstance(mc, integrate.faceted_ellipsoid_union):
            cls = _hpmc.UpdaterMuVTFacetedEllipsoidUnion;
        elif isinstance(mc, integrate.polyhedron):
            cls =_hpmc.UpdaterMuVTPolyhedron;
        else:
            hoomd.context.current.device.cpp_msg.error("update.muvt: Unsupported integrator.\n");
            raise RuntimeError("Error initializing update.muvt");

        self.cpp_updater = cls(hoomd.context.current.system_definition,
                               mc.cpp_integrator,
                               int(seed),
                               ngibbs);

        # register the muvt updater
        self.setupUpdater(period);

        # set the list of transferred types
        if not isinstance(transfer_types,list):
            hoomd.context.current.device.cpp_msg.error("update.muvt: Need list of types to transfer.\n");
            raise RuntimeError("Error initializing update.muvt");

        cpp_transfer_types = _hoomd.std_vector_uint();
        for t in transfer_types:
            if t not in type_list:
                hoomd.context.current.device.cpp_msg.error("Trying to transfer unknown type " + str(t) + "\n");
                raise RuntimeError("Error setting muVT parameters");
            else:
                type_id = hoomd.context.current.system_definition.getParticleData().getTypeByName(t);

            cpp_transfer_types.append(type_id)

        self.cpp_updater.setTransferTypes(cpp_transfer_types)

    def set_fugacity(self, type, fugacity):
        R""" Change muVT fugacities.

        Args:
            type (str): Particle type to set parameters for
            fugacity (float): Fugacity of this particle type (dimension of volume^-1)

        Example::

            muvt = hpmc.update.muvt(mc, period=10)
            muvt.set_fugacity(type='A', fugacity=1.23)
            variant = hoomd.variant.linear_interp(points=[(0,1e1), (1e5, 4.56)])
            muvt.set_fugacity(type='A', fugacity=variant)

        """
        self.check_initialization();

        if self.gibbs:
            raise RuntimeError("Gibbs ensemble does not support setting the fugacity.\n");

        # get a list of types from the particle data
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        if type not in type_list:
            hoomd.context.current.device.cpp_msg.error("Trying to set fugacity for unknown type " + str(type) + "\n");
            raise RuntimeError("Error setting muVT parameters");
        else:
            type_id = hoomd.context.current.system_definition.getParticleData().getTypeByName(type);

        fugacity_variant = hoomd.variant._setup_variant_input(fugacity);
        self.cpp_updater.setFugacity(type_id, fugacity_variant.cpp_variant);

    def set_params(self, dV=None, volume_move_probability=None, n_trial=None):
        R""" Set muVT parameters.

        Args:
            dV (float): (if set) Set volume rescaling factor (dimensionless)
            volume_move_probability (float): (if set) In the Gibbs ensemble, set the
                probability of volume moves (other moves are exchange/transfer moves).
            n_trial (int): (if set) Number of re-insertion attempts per depletant

        Example::

            muvt = hpmc.update.muvt(mc, period = 10)
            muvt.set_params(dV=0.1)
            muvt.set_params(n_trial=2)
            muvt.set_params(volume_move_probability=0.05)

        """
        self.check_initialization();

        if volume_move_probability is not None:
            if not self.gibbs:
                hoomd.context.current.device.cpp_msg.warning("Move ratio only used in Gibbs ensemble.\n");
            self.cpp_updater.setVolumeMoveProbability(float(volume_move_probability))

        if dV is not None:
            if not self.gibbs:
                hoomd.context.current.device.cpp_msg.warning("Parameter dV only available for Gibbs ensemble.\n");
            self.cpp_updater.setMaxVolumeRescale(float(dV))

        if n_trial is not None:
            self.cpp_updater.setNTrial(int(n_trial))


class remove_drift(_updater):
    R""" Remove the center of mass drift from a system restrained on a lattice.

    Args:
        mc (:py:mod:`hoomd.hpmc.integrate`): MC integrator.
        external_lattice (:py:class:`hoomd.hpmc.field.lattice_field`): lattice field where the lattice is defined.
        period (int): the period to call the updater

    The command hpmc.update.remove_drift sets up an updater that removes the center of mass
    drift of a system every period timesteps,

    Example::

        mc = hpmc.integrate.convex_polyhedron(seed=seed);
        mc.shape_param.set("A", vertices=verts)
        mc.set_params(d=0.005, a=0.005)
        lattice = hpmc.compute.lattice_field(mc=mc, position=fcc_lattice, k=1000.0);
        remove_drift = update.remove_drift(mc=mc, external_lattice=lattice, period=1000);

    """
    def __init__(self, mc, external_lattice, period=1):
        #initialize base class
        _updater.__init__(self);
        cls = None;
        if not hoomd.context.current.device.cpp_exec_conf.isCUDAEnabled():
            if isinstance(mc, integrate.sphere):
                cls = _hpmc.RemoveDriftUpdaterSphere;
            elif isinstance(mc, integrate.convex_polygon):
                cls = _hpmc.RemoveDriftUpdaterConvexPolygon;
            elif isinstance(mc, integrate.simple_polygon):
                cls = _hpmc.RemoveDriftUpdaterSimplePolygon;
            elif isinstance(mc, integrate.convex_polyhedron):
                cls = _hpmc.RemoveDriftUpdaterConvexPolyhedron;
            elif isinstance(mc, integrate.convex_spheropolyhedron):
                cls = _hpmc.RemoveDriftUpdaterSpheropolyhedron;
            elif isinstance(mc, integrate.ellipsoid):
                cls = _hpmc.RemoveDriftUpdaterEllipsoid;
            elif isinstance(mc, integrate.convex_spheropolygon):
                cls =_hpmc.RemoveDriftUpdaterSpheropolygon;
            elif isinstance(mc, integrate.faceted_sphere):
                cls =_hpmc.RemoveDriftUpdaterFacetedEllipsoid;
            elif isinstance(mc, integrate.polyhedron):
                cls =_hpmc.RemoveDriftUpdaterPolyhedron;
            elif isinstance(mc, integrate.sphinx):
                cls =_hpmc.RemoveDriftUpdaterSphinx;
            elif isinstance(mc, integrate.sphere_union):
                cls = _hpmc.RemoveDriftUpdaterSphereUnion;
            elif isinstance(mc, integrate.convex_spheropolyhedron_union):
                cls = _hpmc.RemoveDriftUpdaterConvexPolyhedronUnion;
            elif isinstance(mc, integrate.faceted_ellipsoid_union):
                cls = _hpmc.RemoveDriftUpdaterFacetedEllipsoidUnion;
            else:
                hoomd.context.current.device.cpp_msg.error("update.remove_drift: Unsupported integrator.\n");
                raise RuntimeError("Error initializing update.remove_drift");
        else:
            raise RuntimeError("update.remove_drift: Error! GPU not implemented.");

        self.cpp_updater = cls(hoomd.context.current.system_definition, external_lattice.cpp_compute, mc.cpp_integrator);
        self.setupUpdater(period);


class ShapeUpdater(Updater):
    """Apply shape updates to the shape definitions defined in the integrator.

    Args:
        mc (:py:mod:`hoomd.hpmc.integrate.HPMCIntegrator`): HPMC integrator object for system on which to apply box updates

        move_ratio (:py:class:`float` or :py:mod:`hoomd.variant`): Fraction of steps to run the updater.

        seed (int): Random number seed for shape move generators

        trigger (Trigger, **default:** hoomd.trigger.Periodic(1)): Call the updater on triggered time steps.

        pretend (bool, **default:** False): When True the updater will not actually make update the shape definitions, instead moves will be proposed and
                        the acceptance statistics will be updated correctly

        nselect (int, **default:** 1): Number of types to change every time the updater is called.

        nsweeps (int, **default:** 1): Number of times to change nselect types every time the updater is called.

        multi_phase (bool, **default:** False): When True MPI is enforced and shapes are updated together for two boxes.

        num_phase (int, **default:** 1): How many boxes are simulated at the same time, now support 2 and 3.

    This class should not be instantiated directly - instead the Alchemy and ElasticShape 
    classes should be. Each updater defines a specific statistical ensemble. Shape moves 
    will update the shape definitions for every type. See the different updaters for 
    documentation on the specific acceptance criteria and examples.

    Note:
        Only one of the Monte Carlo move types are applied to evolve the particle shape definition. By default, no moves are applied.
        Activate desired move types using the following methods.

        - :py:meth:`python_shape_move` - supply a python call back that will take a list of parameters between 0 and 1 and return a shape param object.
        - :py:meth:`vertex_shape_move` - make changes to the the vertices of the shape definition. Currently only defined for convex polyhedra.
        - :py:meth:`constant_shape_move` - make a single move to a shape i.e. shape_old -> shape_new. Useful when pretend is set to True.
        - :py:meth:`elastic_shape_move` - scale and shear the particle definitions. Currently only defined for ellipsoids and convex polyhedra.

        See the documentation for the individual moves for more usage information.

    Examples::
        mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
        mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                       (-1, 1, -1)])
        updater = hoomd.hpmc.update.Alchemy(mc=mc, move_ratio=1.0, seed=3832765, trigger=hoomd.trigger.Periodic(1), nselect=1)

    Attributes:
        mc (:py:mod:`hoomd.hpmc.integrate.HPMCIntegrator`): HPMC integrator object for system on which to apply box updates

        move_ratio (:py:class:`float` or :py:mod:`hoomd.variant`): Fraction of steps to run the updater.

        seed (int): Random number seed for shape move generators

        trigger (Trigger): Call the updater on triggered time steps.

        pretend (bool): When True the updater will not actually make update the shape definitions, instead moves will be proposed and
                        the acceptance statistics will be updated correctly

        nselect (int): Number of types to change every time the updater is called.

        nsweeps (int): Number of times to change nselect types every time the updater is called.

        multi_phase (bool): When True MPI is enforced and shapes are updated together for two boxes.

        num_phase (int): How many boxes are simulated at the same time, now support 2 and 3.
    """
    def __init__(   self,
                    mc,
                    move_ratio,
                    seed,
                    trigger=hoomd.trigger.Periodic(1),
                    pretend=False,
                    nselect=1,
                    nsweeps=1,
                    multi_phase=False,
                    num_phase=1):

        super().__init__(trigger)

        param_dict = ParameterDict(mc=hoomd.hpmc.integrate.HPMCIntegrator,
                                   move_ratio=float,
                                   seed=int,
                                   pretend=bool,
                                   nselect=int,
                                   nsweeps=int,
                                   multi_phase=bool,
                                   num_phase=int)
        param_dict['mc'] = mc
        param_dict['move_ratio'] = move_ratio
        param_dict['seed'] = seed
        param_dict['pretend'] = pretend
        param_dict['nselect'] = nselect
        param_dict['nsweeps'] = nsweeps
        param_dict['multi_phase'] = multi_phase
        param_dict['num_phase'] = num_phase

        self._param_dict.update(param_dict)
        self._cpp_obj = None
        self.move_cpp = None

    def _attach(self):
        integrator = self._simulation.operations.integrator
        if not isinstance(integrator, integrate.HPMCIntegrator):
            raise RuntimeError("The integrator must be a HPMC integrator.")

        if not integrator._attached:
            raise RuntimeError("Integrator is not attached yet.")

        cls = None
        if isinstance(self.mc, integrate.Sphere):
            cls = _hpmc.UpdaterShapeSphere
        elif isinstance(self.mc, integrate.ConvexPolygon):
            cls = _hpmc.UpdaterShapeConvexPolygon
        elif isinstance(self.mc, integrate.SimplePolygon):
            cls = _hpmc.UpdaterShapeSimplePolygon
        elif isinstance(self.mc, integrate.ConvexPolyhedron):
            cls = _hpmc.UpdaterShapeConvexPolyhedron
        elif isinstance(self.mc, integrate.ConvexSpheropolyhedron):
            cls = _hpmc.UpdaterShapeSpheropolyhedron
        elif isinstance(self.mc, integrate.Ellipsoid):
            cls = _hpmc.UpdaterShapeEllipsoid
        elif isinstance(self.mc, integrate.ConvexSpheropolygon):
            cls = _hpmc.UpdaterShapeSpheropolygon
        elif isinstance(self.mc, integrate.Polyhedron):
            cls = _hpmc.UpdaterShapePolyhedron
        elif isinstance(self.mc, integrate.Sphinx):
            cls = _hpmc.UpdaterShapeSphinx
        elif isinstance(self.mc, integrate.SphereUnion):
            cls = _hpmc.UpdaterShapeSphereUnion
        else:
            hoomd.context.current.device.cpp_msg.error("update.shape_update: " /
                                                       "Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")
        # TODO: Make this possible
        # Currently computing the moments of inertia for spheropolyhedra is not implemented
        # In order to prevent improper usage, we throw an error here. The use of this
        # updater with spheropolyhedra is currently enabled to allow the use of spherical
        # depletants
        if isinstance(self.mc, integrate.ConvexSpheropolyhedron):
            for typ in self.mc.type_shapes:
                if typ['sweep_radius'] != 0 and len(typ['vertices']) > 1:
                    raise RuntimeError("Currently alchemical moves with integrate.convex_spheropolyhedron \
are only enabled for polyhedral and spherical particles.")
        self._cpp_obj = cls(self._simulation.state._cpp_sys_def,
                            integrator._cpp_obj,
                            self.move_ratio,
                            self.seed,
                            self.nselect,
                            self.nsweeps,
                            self.pretend,
                            self.multi_phase,
                            self.num_phase)
        self._cpp_obj.registerLogBoltzmannFunction(self.boltzmann_function)
        self._cpp_obj.registerShapeMove(self.move_cpp)
        super()._attach()

    def python_shape_move(self, callback, params, stepsize, param_ratio):
        R"""Enable python shape move and set parameters.
        All python shape moves must be callable object that take a single list
        of parameters between 0 and 1 as the call arguments and returns a
        shape parameter definition.

        Args:
            callback (callable): The python function that will be called each update.
            params (dict): Dictionary of types and the corresponding list parameters ({'A' : [1.0], 'B': [0.0]})
            stepsize (float): Step size in parameter space.
            param_ratio (float): Average fraction of parameters to change each update

        Note:
            Parameters must be given for every particle type. Callback should rescale the particle to have constant
            volume if necessary/desired.

        Example::

            # example callback
            class convex_polyhedron_callback:
                def __init__(self, mc):
                    self.mc = mc;
                def __call__(self, params):
                    # do something with params and define verts
                    return hoomd.hpmc._hpmc.PolyhedronVertices(verts)
            mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
            mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                           (-1, 1, -1)])

            # now set up the updater
            shape_up = hpmc.update.Alchemy(mc, move_ratio=0.25, seed=9876)
            shape_up.python_shape_move(callback=convex_polyhedron_callback(mc), params={'A': [0.5]}, stepsize=0.001, param_ratio=0.5)

        """
        if self.move_cpp is not None:
            # hoomd.context.current.device.cpp_msg.error("update.shape_update.python_shape_move: Cannot change the move once initialized.\n")
            raise RuntimeError("Error initializing update.shape_update")
        move_cls = None
        if isinstance(self.mc, integrate.Sphere):
            move_cls = _hpmc.PythonShapeMoveSphere
        elif isinstance(self.mc, integrate.ConvexPolygon):
            move_cls = _hpmc.PythonShapeMoveConvexPolygon
        elif isinstance(self.mc, integrate.SimplePolygon):
            move_cls = _hpmc.PythonShapeMoveSimplePolygon
        elif isinstance(self.mc, integrate.ConvexPolyhedron):
            move_cls = _hpmc.PythonShapeMoveConvexPolyhedron
        elif isinstance(self.mc, integrate.ConvexSpheropolyhedron):
            move_cls = _hpmc.PythonShapeMoveSpheropolyhedron
        elif isinstance(self.mc, integrate.Ellipsoid):
            move_cls = _hpmc.PythonShapeMoveEllipsoid
        elif isinstance(self.mc, integrate.ConvexSpheropolygon):
            move_cls = _hpmc.PythonShapeMoveConvexSphereopolygon
        elif isinstance(self.mc, integrate.Polyhedron):
            move_cls = _hpmc.PythonShapeMovePolyhedron
        elif isinstance(self.mc, integrate.Sphinx):
            move_cls = _hpmc.PythonShapeMoveSphinx
        elif isinstance(self.mc, integrate.SphereUnion):
            move_cls = _hpmc.PythonShapeMoveSphereUnion
        else:
            # hoomd.context.current.device.cpp_msg.error("update.shape_update.python_shape_move: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        if not move_cls:
            # hoomd.context.current.device.cpp_msg.error("update.shape_update.python_shape_move: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        param_list = []
        types = list(self.mc.state["shape"].keys())
        ntypes = len(types) - 1
        for i in range(ntypes):
            if types[i] != '__default__':
                param_list.append(params[types[i]])

        if isinstance(stepsize, float) or isinstance(stepsize, int):
            stepsize_list = [float(stepsize) for i in range(ntypes)]
        else:
            stepsize_list = self.mc.shape_class.ensure_list(stepsize)
        self.move_cpp = move_cls(ntypes, callback, param_list, stepsize_list, float(param_ratio))

    def vertex_shape_move(self, stepsize, param_ratio, volume=1.0):
        R"""
        Enable vertex shape move and set parameters. Changes a particle shape by
        translating vertices and rescaling to have constant volume. The shape definition
        corresponds to the convex hull of the vertices.

        Args:
            stepsize (float): Stepsize for each vertex move
            param_ratio (float): Average fraction of vertices to change each update
            volume (float, **default:** 1.0): Volume of the particles to hold constant

        Example::

            mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
            mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                           (-1, 1, -1)])
            shape_up = hpmc.update.Alchemy(mc, move_ratio=0.25, seed=9876)
            shape_up.vertex_shape_move(stepsize=0.001, param_ratio=0.25, volume=1.0)

        """
        if self.move_cpp is not None:
            hoomd.context.current.device.cpp_msg.error("update.shape_update.vertex_shape_move: Cannot change the move once initialized.\n")
            raise RuntimeError("Error initializing update.shape_update")
        move_cls = None
        if isinstance(self.mc, integrate.Sphere):
            pass
        elif isinstance(self.mc, integrate.ConvexPolygon):
            pass
        elif isinstance(self.mc, integrate.SimplePolygon):
            pass
        elif isinstance(self.mc, integrate.ConvexPolyhedron):
            move_cls = _hpmc.GeneralizedShapeMoveConvexPolyhedron
        elif isinstance(self.mc, integrate.ConvexSpheropolyhedron):
            pass
        elif isinstance(self.mc, integrate.Ellipsoid):
            pass
        elif isinstance(self.mc, integrate.ConvexSpheropolygon):
            pass
        elif isinstance(self.mc, integrate.Polyhedron):
            pass
        elif isinstance(self.mc, integrate.Sphinx):
            pass
        elif isinstance(self.mc, integrate.SphereUnion):
            pass
        else:
            hoomd.context.current.device.cpp_msg.error("update.shape_update.vertex_shape_move: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        if not move_cls:
            hoomd.context.current.device.cpp_msg.error("update.shape_update: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        ntypes = len(self.mc.state["shape"].keys()) - 1
        self.move_cpp = move_cls(ntypes, stepsize, param_ratio, volume)

    def constant_shape_move(self, **shape_params):
        R"""
        Enable constant shape move and set parameters. Changes a particle shape by
        the same way every time the updater is called. This is useful for calculating
        a specific transition probability and derived thermodynamic quantities.

        Args:
            shape_params: Arguments required to define the hoomd.hpmc.integrate reference shape. 

        Example::
            mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
            mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                           (-1, 1, -1)])
            shape_up = hpmc.update.Alchemy(mc, move_ratio=0.25, seed=9876)
            # convex_polyhedron
            shape_up.constant_shape_move(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                                   (-1, 1, -1)])

        See Also:
            :py:mod:`hoomd.hpmc.integrate` for required shape parameters.

        """
        if self.move_cpp is not None:
            hoomd.context.current.device.cpp_msg.error("update.shape_update.constant_shape_move: Cannot change the move once initialized.\n")
            raise RuntimeError("Error initializing update.shape_update")
        move_cls = None
        shape_cls = None
        if isinstance(self.mc, integrate.Sphere):
            move_cls = _hpmc.ConstantShapeMoveSphere
            shape_cls = hoomd.hpmc._hpmc.SphereParams
        elif isinstance(self.mc, integrate.ConvexPolygon):
            move_cls = _hpmc.ConstantShapeMoveConvexPolygon
            shape_cls = hoomd.hpmc._hpmc.PolygonVertices
        elif isinstance(self.mc, integrate.SimplePolygon):
            move_cls = _hpmc.ConstantShapeMoveSimplePolygon
            shape_cls = hoomd.hpmc._hpmc.PolygonVertices
        elif isinstance(self.mc, integrate.ConvexPolyhedron):
            move_cls = _hpmc.ConstantShapeMoveConvexPolyhedron
            shape_cls = hoomd.hpmc._hpmc.PolyhedronVertices
        elif isinstance(self.mc, integrate.ConvexSpheropolyhedron):
            move_cls = _hpmc.ConstantShapeMoveSpheropolyhedron
            shape_cls = hoomd.hpmc._hpmc.PolyhedronVertices
        elif isinstance(self.mc, integrate.Ellipsoid):
            move_cls = _hpmc.ConstantShapeMoveEllipsoid
            shape_cls = hoomd.hpmc._hpmc.EllipsoidParams
        elif isinstance(self.mc, integrate.ConvexSpheropolygon):
            move_cls = _hpmc.ConstantShapeMoveConvexSphereopolygon
            shape_cls = hoomd.hpmc._hpmc.PolygonVertices
        elif isinstance(self.mc, integrate.Polyhedron):
            move_cls = _hpmc.ConstantShapeMovePolyhedron
            shape_cls = hoomd.hpmc._hpmc.PolyhedronVertices
        elif isinstance(self.mc, integrate.Sphinx):
            move_cls = _hpmc.ConstantShapeMoveSphinx
            shape_cls = hoomd.hpmc._hpmc.SphinxParams
        elif isinstance(self.mc, integrate.SphereUnion):
            move_cls = _hpmc.ConstantShapeMoveSphereUnion
            shape_cls = hoomd.hpmc._hpmc.SphereUnionParams
        else:
            hoomd.context.current.device.cpp_msg.error("update.shape_update.constant_shape_move: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        if not move_cls:
            hoomd.context.current.device.cpp_msg.error("update.shape_update.constant_shape_move: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        ntypes = len(self.mc.state["shape"].keys()) - 1
        self.move_cpp = move_cls(ntypes, [shape_cls(shape_params)] * ntypes)

    def elastic_shape_move(self, stepsize, param_ratio=0.5):
        R"""
        Enable scale and shear shape move and set parameters. Changes a particle shape by
        scaling the particle and shearing the particle.

        Args:
            stepsize (float): Largest scaling/shearing factor used.
            param_ratio (float, **default:** 0.5): Fraction of scale to shear moves.

        Example::
            mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
            mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                           (-1, 1, -1)])
            shape_up = hpmc.update.Alchemy(mc, param_ratio=0.25, seed=9876)
            shape_up.elastic_shape_move(stepsize=0.01)

        """
        if self.move_cpp is not None:
            hoomd.context.current.device.cpp_msg.error("update.shape_update.elastic_shape_move: Cannot change the move once initialized.\n")
            raise RuntimeError("Error initializing update.shape_update")
        move_cls = None
        if isinstance(self.mc, integrate.ConvexPolyhedron):
            move_cls = _hpmc.ElasticShapeMoveConvexPolyhedron
        elif isinstance(self.mc, integrate.Ellipsoid):
            move_cls = _hpmc.ElasticShapeMoveEllipsoid
        else:
            hoomd.context.current.device.cpp_msg.error("update.shape_update.elastic_shape_move: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        if not move_cls:
            hoomd.context.current.device.cpp_msg.error("update.shape_update.elastic_shape_move: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        ntypes = len(self.mc.state["shape"].keys()) - 1
        self.move_cpp = move_cls(ntypes, stepsize, param_ratio)

    def get_tuner(self, target, trigger, max_scale=2., gamma=1., tol=1e-2):
        R""" Returns a :py:mod:`hoomd.tune.CustomTuner` object set to tune the step size of the shape move.
        Args:
            target (float): Target shape move acceptance ratio
            trigger (Trigger): Call the updater on triggered time steps.
            max_scale (float, **default:** 2.0): The maximum amount to scale the
                current step size value with
            gamma (float, **default:** 1.0): nonnegative real number used to dampen
                or increase the rate of change in step size. ``gamma`` is added to the
                numerator and denominator of the ``acceptance_ratio / target`` ratio. Larger values
                of ``gamma`` lead to smaller changes while a ``gamma`` of 0 leads to
                scaling step size by exactly the ``acceptance_ratio / target`` ratio.
            tol (float, **default:** 0.01): The absolute tolerance for convergence of acceptance_ratio

        Example::

            mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
            mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                           (-1, 1, -1)])
            shape_up = hpmc.update.Alchemy(mc, move_ratio=0.25, seed=9876)
            shape_up.vertex_shape_move(stepsize=0.001, param_ratio=0.25, volume=1.0)
            tuner = shape_up.get_tuner(0.25, hoomd.trigger.Periodic(1))
        """

        def get_y():
            acc = 0.0
            if self.total_count > 0:
                acc = float(self.accepted_count) / float(self.total_count)
            return acc

        def get_x():
            return self._cpp_obj.getStepSize(0)

        def set_x(stepsize):
            return self._cpp_obj.setStepSize(0, stepsize)

        tuneables = [hoomd.tune.ManualTuneDefinition(get_y, target, get_x, set_x)]
        tuneables[0].domain = (0.0, 0.5)
        solver = hoomd.tune.attr_tuner.ScaleSolver(max_scale, gamma, 'negative', tol)

        class TuneAction(Action):
            def __init__(cls, tuneables):
                cls.tuneables = tuneables
                cls.tuned = None
            def act(cls, timestep):
                cls.tuned = solver.solve(cls.tuneables)
        tuner = hoomd.tune.CustomTuner(TuneAction(tuneables), trigger)
        return tuner

    @property
    def total_count(self):
        """Total number of shape moves attempted
        """
        return sum([self._cpp_obj.getTotalCount(i) for i in range(self._simulation.state._cpp_sys_def.getParticleData().getNTypes())])

    @property
    def accepted_count(self):
        """Total number of shape moves accepted
        """
        return sum([self._cpp_obj.getAcceptedCount(i) for i in range(self._simulation.state._cpp_sys_def.getParticleData().getNTypes())])

    @log(flag='scalar')
    def shape_move_acceptance_ratio(self):
        """float: Returns the shape move acceptance ratio for all particle types

        Returns:
            The combined shape move acceptance ratio for all particle types
        """
        acc = 0.0
        if self.total_count > 0:
            acc = float(self.accepted_count) / float(self.total_count)
        return acc

    @log(flag='scalar')
    def shape_move_particle_volume(self):
        """float: Returns the total volume being occupied by particles.

        Returns:
            The current value of the total volume occupied by particles
        """
        return sum([self._cpp_obj.getParticleVolume(i) for i in range(self._simulation.state._cpp_sys_def.getParticleData().getNTypes())])

    @log(flag='scalar')
    def shape_param(self):
        """float: Returns the shape parameter value being used in :py:mod:`python_shape_move`. Returns 0 if another shape move is being used.

        Returns:
            The current value of the shape parameter in the user-specified callback
        """
        if 'Python' in str(self.move_cpp):
            return self._cpp_obj.getShapeParam("shape_param-0", self._simulation.timestep)
        return 0.0

    def get_step_size(self, typeid=0):
        R""" Get the shape move stepsize for a particle type

        Args:
            typeid (int, **default:** 0): The typeid of the particle type
        Returns:
            The shape move stepsize for a particle type

        Example::

            mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
            mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                           (-1, 1, -1)])
            shape_updater = hpmc.update.Alchemy(mc, move_ratio=0.25, seed=9876)
            stepsize = shape_updater.get_step_size(0)

        """
        return self._cpp_obj.getStepSize(typeid)

    def reset_statistics(self):
        R""" Reset the acceptance statistics for the updater
        Example::

            mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
            mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                           (-1, 1, -1)])
            shape_updater = hpmc.update.Alchemy(mc, move_ratio=0.25, seed=9876)
            stepsize = shape_updater.reset_statistics()
        """

        self._cpp_obj.resetStatistics()


class Alchemy(ShapeUpdater):
    R""" Apply vertex, constant, and python shape moves.

    Args:
        params: Arguments required to initialize :py:mod:`hoomd.hpmc.update.shape_update`

    Users should instantiate this class before calling one of the :py:mod:`vertex_shape_move`,
    :py:mod:`python_shape_move`, and :py:mod:`constant_shape_move` methods.

    Example::

        mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
        mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                       (-1, 1, -1)])
        shape_up = hpmc.update.Alchemy(mc, move_ratio=0.25, seed=9876)

    """
    def __init__(   self,
                    **params):

        # initialize base class
        super().__init__(**params)
        boltzmann_cls = None
        if isinstance(self.mc, integrate.Sphere):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannSphere
        elif isinstance(self.mc, integrate.ConvexPolygon):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannConvexPolygon
        elif isinstance(self.mc, integrate.SimplePolygon):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannSimplePolygon
        elif isinstance(self.mc, integrate.ConvexPolyhedron):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannConvexPolyhedron
        elif isinstance(self.mc, integrate.ConvexSpheropolyhedron):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannSpheropolyhedron
        elif isinstance(self.mc, integrate.Ellipsoid):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannEllipsoid
        elif isinstance(self.mc, integrate.ConvexSpheropolygon):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannSpheropolygon
        elif isinstance(self.mc, integrate.Polyhedron):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannPolyhedron
        elif isinstance(self.mc, integrate.Sphinx):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannSphinx
        elif isinstance(self.mc, integrate.SphereUnion):
            boltzmann_cls = _hpmc.AlchemyLogBoltzmannSphereUnion
        else:
            hoomd.context.current.device.cpp_msg.error("update.shape_update: Unsupported integrator.\n")
            raise RuntimeError("Error initializing update.shape_update")

        self.boltzmann_function = boltzmann_cls()

class ElasticShape(ShapeUpdater):
    R""" Apply elastic shape moves.

    Args:
        stiffness (float): Stiffness of the particle spring
        reference (dict): Arguments required to define the hoomd.hpmc.integrate reference shape. 
        stepsize (float): Largest scaling/shearing factor used.
        param_ratio (float): Fraction of scale to shear moves.
        params (dict): The parameters required to initialize :py:mod:`hoomd.hpmc.update.ShapeUpdater`

    Shears a shape and calculates acceptance based on the sheared shape's energy. Shape volume 
    remains constant during shearing.

    Example::

        mc = hoomd.hpmc.integrate.ConvexPolyhedron(23456)
        mc.shape["A"] = dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),
                                       (-1, 1, -1)])
        updater_params = {'mc': mc, 'seed': 1, 'move_ratio': 0.5}
        elastic = hpmc.update.ElasticShape(stiffness=10.0,
                                           reference=dict(vertices=[(1, 1, 1), (-1, -1, 1), (1, -1, -1),(-1, 1, -1)]),
                                           stepsize=0.1,
                                           param_ratio=0.5,
                                           params=updater_params)
    """

    def __init__(self,
                 stiffness,
                 reference,
                 stepsize,
                 param_ratio,
                 params):
        defaults = {"trigger": hoomd.trigger.Periodic(1),
                    "pretend": False,
                    "nselect": 1,
                    "nsweeps": 1,
                    "multi_phase": False,
                    "num_phase": 1}
        for arg, val in defaults.items():
            if arg not in params:
                params[arg] = val
        # initialize base class
        super().__init__(params["mc"],
                         params["move_ratio"],
                         params["seed"],
                         params["trigger"],
                         params["pretend"],
                         params["nselect"],
                         params["nsweeps"],
                         params["multi_phase"],
                         params["num_phase"])
                          # mc, move_ratio, seed,
        param_dict = ParameterDict(mc=hoomd.hpmc.integrate.HPMCIntegrator,
                                   move_ratio=float,
                                   seed=int,
                                   pretend=bool,
                                   nselect=int,
                                   nsweeps=int,
                                   multi_phase=bool,
                                   num_phase=int,
                                   stiffness=hoomd.variant.Variant,
                                   reference=dict,
                                   stepsize=float,
                                   param_ratio=float)
        for key, val in params.items():
            param_dict[key] = val            

        param_dict['reference'] = reference
        param_dict['stepsize'] = stepsize
        param_dict['param_ratio'] = param_ratio

        if type(stiffness) in [int, float]:
            stiffness = hoomd.variant.Constant(stiffness)
        param_dict['stiffness'] = stiffness

        self._param_dict.update(param_dict)

        self.elastic_shape_move(stepsize, param_ratio)

        # if hoomd.context.current.device.cpp_exec_conf.isCUDAEnabled():
        #     hoomd.context.current.device.cpp_msg.warning("update.elastic_shape: GPU is not implemented defaulting to CPU implementation.\n")
        shape_cls = None
        if isinstance(self.mc, integrate.ConvexPolyhedron):
            clss = _hpmc.ShapeSpringLogBoltzmannConvexPolyhedron
            shape_cls = hoomd.hpmc._hpmc.PolyhedronVertices
        elif isinstance(self.mc, integrate.Ellipsoid):
            for type_shape in self.mc.type_shapes():
                if not np.isclose(type_shape["a"], type_shape["b"]) or \
                   not np.isclose(type_shape["a"], type_shape["c"]) or \
                   not np.isclose(type_shape["b"], type_shape["c"]):
                    raise ValueError("This updater only works when a=b=c initially.")
            clss = _hpmc.ShapeSpringLogBoltzmannEllipsoid
            shape_cls = hoomd.hpmc._hpmc.EllipsoidParams
        else:
            hoomd.context.current.device.cpp_msg.error("update.elastic_shape: Unsupported integrator.\n")
            raise RuntimeError("Error initializing compute.elastic_shape")

        ref_shape = shape_cls(reference)
        self.boltzmann_function = clss(self.stiffness, ref_shape, self.move_cpp)

    def set_stiffness(self, stiffness):
        R""" Update the stiffness set point for Metropolis Monte Carlo elastic shape updates.

        Args:
            stiffness (float) or (:py:mod:`hoomd.variant`): :math:`\frac{k}/{k_{\mathrm{B}}T}`.
        """
        if type(stiffness) in [int, float]:
            stiffness = hoomd.variant.Constant(stiffness)
        self.stiffness = stiffness
        self.boltzmann_function.setStiffness(self.stiffness)

    @log(flag="scalar")
    def shape_move_stiffness(self):
        """float: Stiffness of the shape used to calculate shape energy

        Returns:
            The stiffness of the shape at the current timestep
        """
        return self._param_dict["stiffness"](self._simulation.timestep)

    @log(flag="scalar")
    def shape_move_energy(self):
        """float: Energy of the shape resulting from shear moves

        Returns:
            The energy of the shape at the current timestep
        """
        return sum([self._cpp_obj.getShapeMoveEnergy(i, self._simulation.timestep) for i in range(self._simulation.state._cpp_sys_def.getParticleData().getNTypes())])


class Clusters(Updater):
    """Apply geometric cluster algorithm (GCA) moves.

    Args:
        seed (int): Random number seed.
        swap_types (list[tuple[str, str]]): A pair of two types whose identities
            may be swapped.
        move_ratio (float): Set the ratio between pivot and reflection moves.
        flip_probability (float): Set the probability for transforming an
                                 individual cluster.
        swap_move_ratio (float): Set the ratio between type swap moves and
                                geometric moves.
        trigger (Trigger): Select the timesteps on which to perform cluster
            moves.

    The GCA as described in Liu and Lujten (2004),
    http://doi.org/10.1103/PhysRevLett.92.035504 is used for hard shape, patch
    interactions and depletants.

    With depletants, Clusters are defined by a simple distance cut-off
    criterion. Two particles belong to the same cluster if the circumspheres of
    the depletant-excluded volumes overlap.

    Supported moves include pivot moves (point reflection), line reflections
    (pi rotation around an axis), and type swaps.  Only the pivot move is
    rejection free. With anisotropic particles, the pivot move cannot be used
    because it would create a chiral mirror image of the particle, and only
    line reflections are employed. Line reflections are not rejection free
    because of periodic boundary conditions, as discussed in Sinkovits et al.
    (2012), http://doi.org/10.1063/1.3694271.

    The type swap move works between two types of spherical particles and
    exchanges their identities.

    .. rubric:: Threading

    The `Clusters` updater support threaded execution on multiple CPU cores.

    Attributes:
        seed (int): Random number seed.
        swap_types (list): A pair of two types whose identities may be swapped.
        move_ratio (float): Set the ratio between pivot and reflection moves.
        flip_probability (float): Set the probability for transforming an
                                 individual cluster.
        swap_move_ratio (float): Set the ratio between type swap moves and
                                geometric moves.
        trigger (Trigger): Select the timesteps on which to perform cluster
            moves.
    """

    def __init__(self, seed, swap_types, move_ratio=0.5,
                 flip_probability=0.5, swap_move_ratio=0.5, trigger=1):
        super().__init__(trigger)
        try:
            if len(swap_types) != 2 and len(swap_types) != 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("swap_types must be an iterable of length "
                             "2 or 0.")

        param_dict = ParameterDict(seed=int(seed),
                                   swap_types=list(swap_types),
                                   move_ratio=float(move_ratio),
                                   flip_probability=float(flip_probability),
                                   swap_move_ratio=float(swap_move_ratio))
        self._param_dict.update(param_dict)

    def _attach(self):
        integrator = self._simulation.operations.integrator
        if not isinstance(integrator, integrate.HPMCIntegrator):
            raise RuntimeError("The integrator must be a HPMC integrator.")

        integrator_pairs = [
                (integrate.Sphere,
                    _hpmc.UpdaterClustersSphere),
                (integrate.convex_polygon,
                    _hpmc.UpdaterClustersConvexPolygon),
                (integrate.simple_polygon,
                    _hpmc.UpdaterClustersConvexPolygon),
                (integrate.convex_polyhedron,
                    _hpmc.UpdaterClustersConvexPolyhedron),
                (integrate.convex_spheropolyhedron,
                    _hpmc.UpdaterClustersSpheropolyhedron),
                (integrate.ellipsoid,
                    _hpmc.UpdaterClustersEllipsoid),
                (integrate.convex_spheropolygon,
                    _hpmc.UpdaterClustersSpheropolygon),
                (integrate.faceted_sphere,
                    _hpmc.UpdaterClustersFacetedEllipsoid),
                (integrate.sphere_union,
                    _hpmc.UpdaterClustersSphereUnion),
                (integrate.convex_spheropolyhedron_union,
                    _hpmc.UpdaterClustersConvexPolyhedronUnion),
                (integrate.faceted_ellipsoid_union,
                    _hpmc.UpdaterClustersFacetedEllipsoidUnion),
                (integrate.polyhedron,
                    _hpmc.UpdaterClustersPolyhedron),
                (integrate.sphinx,
                    _hpmc.UpdaterClustersSphinx)
                ]

        cpp_cls = None
        for python_integrator, cpp_updater in integrator_pairs:
            if isinstance(integrator, python_integrator):
                cpp_cls = cpp_updater
        if cpp_cls is None:
            raise RuntimeError("Unsupported integrator.\n")

        if not integrator._attached:
            raise RuntimeError("Integrator is not attached yet.")
        self._cpp_obj = cpp_cls(self._simulation.state._cpp_sys_def,
                                integrator._cpp_obj,
                                int(self.seed))
        super()._attach()

    @property
    def counter(self):
        """Get the number of accepted and rejected cluster moves.

        Returns:
            A counter object with pivot, reflection, and swap properties. Each
            property is a list of accepted moves and rejected moves since the
            last run.

        Note:
            `None` when the simulation run has not started.
        """
        if not self._attached:
            return None
        else:
            return self._cpp_obj.getCounters(1)

    @log(flag='sequence')
    def pivot_moves(self):
        """tuple[int, int]: Number of accepted and rejected pivot moves.

        Returns:
            A tuple of (accepted moves, rejected moves) since the last run.
        """
        counter = self.counter
        if counter is None:
            return (0, 0)
        else:
            return counter.pivot

    @log(flag='sequence')
    def reflection_moves(self):
        """tuple[int, int]: Number of accepted and rejected reflection moves.

        Returns:
            A tuple of (accepted moves, rejected moves) since the last run.
        """
        counter = self.counter
        if counter is None:
            return (0, 0)
        else:
            return counter.reflection

    @log(flag='sequence')
    def swap_moves(self):
        """tuple[int, int]: Number of accepted and rejected swap moves.

        Returns:
            A tuple of (accepted moves, rejected moves) since the last run.
        """
        counter = self.counter
        if counter is None:
            return (0, 0)
        else:
            return counter.swap

class QuickCompress(Updater):
    """Quickly compress a hard particle system to a target box.

    Args:
        trigger (Trigger): Update the box dimensions on triggered time steps.

        seed (int): Random number seed.

        target_box (Box): Dimensions of the target box.

        max_overlaps_per_particle (float): The maximum number of overlaps to
            allow per particle (may be less than 1 - e.g.
            up to 250 overlaps would be allowed when in a system of 1000
            particles when max_overlaps_per_particle=0.25).

        min_scale (float): The minimum scale factor to apply to box dimensions.

    Use `QuickCompress` in conjunction with an HPMC integrator to scale the
    system to a target box size. `QuickCompress` can typically compress dilute
    systems to near random close packing densities in tens of thousands of time
    steps.

    It operates by making small changes toward the `target_box`: ``L_new = scale
    * L_current`` for each box parameter (where the smallest value of `scale` is
    `min_scale`) and then scaling the particle positions into the new box. If
    there are more than ``max_overlaps_per_particle * N_particles`` hard
    particle overlaps in the system, the box move is rejected. Otherwise, the
    small number of overlaps remain. `QuickCompress` then waits until local MC
    trial moves provided by the HPMC integrator remove all overlaps before it
    makes another box change.

    Note:
        The target box size may be larger or smaller than the current system
        box, and also may have different tilt factors. When the target box
        parameter is larger than the current, it scales by ``L_new = 1/scale *
        L_current``

    Tip:
        Use the `hoomd.hpmc.tune.MoveSizeTuner` in conjunction with
        `QuickCompress` to adjust the move sizes to maintain a constant
        acceptance ratio as the density of the system increases.

    .. rubric:: Run completion

    When the box reaches the target box size **and** there are no overlaps in
    the current configuration, `QuickCompress` will flag that it is complete,
    which will end the `Simulation.run` loop.

    Note:

        When the `Simulation.run` loop ends after the requested number of steps,
        the final system configuration may include particle overlaps and the box
        size will be somewhere between the initial box and `target_box`.

    Warning:

        If the the requested `target_box` is too small to attain,
        `QuickCompress` will not complete and the `Simulation.run` loop will end
        after the requested number of time steps.

    Attributes:
        trigger (Trigger): Update the box dimensions on triggered time steps.

        seed (int): Random number seed.

        target_box (Box): Dimensions of the target box.

        max_overlaps_per_particle (float): The maximum number of overlaps to
            allow per particle (may be less than 1 - e.g.
            up to 250 overlaps would be allowed when in a system of 1000
            particles when max_overlaps_per_particle=0.25).

        min_scale (float): The minimum scale factor to apply to box dimensions.
    """

    def __init__(self,
                 trigger,
                 target_box,
                 seed,
                 max_overlaps_per_particle=0.25,
                 min_scale=0.99):
        super().__init__(trigger)

        param_dict = ParameterDict(
            seed=int,
            max_overlaps_per_particle=float,
            min_scale=float,
            target_box=hoomd.data.typeconverter.OnlyType(
                hoomd.Box,
                preprocess=hoomd.data.typeconverter.box_preprocessing))
        param_dict['seed'] = seed
        param_dict['max_overlaps_per_particle'] = max_overlaps_per_particle
        param_dict['min_scale'] = min_scale
        param_dict['target_box'] = target_box

        self._param_dict.update(param_dict)

    def _attach(self):
        integrator = self._simulation.operations.integrator
        if not isinstance(integrator, integrate.HPMCIntegrator):
            raise RuntimeError("The integrator must be a HPMC integrator.")

        if not integrator._attached:
            raise RuntimeError("Integrator is not attached yet.")

        self._cpp_obj = _hpmc.UpdaterQuickCompress(
            self._simulation.state._cpp_sys_def, integrator._cpp_obj,
            self.max_overlaps_per_particle, self.min_scale, self.target_box,
            self.seed)
        super()._attach()

    @property
    def complete(self):
        """True when the operation is complete.

        `Simulation.run` stops the running whenever any operation in the
        `Simulation` is complete.
        """
        if not self._attached:
            return False

        return self._cpp_obj.isComplete()
