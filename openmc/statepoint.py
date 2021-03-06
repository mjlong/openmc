import sys
import re
import numpy as np

import openmc

if sys.version > '3':
    long = int


class StatePoint(object):
    """State information on a simulation at a certain point in time (at the end of a
    given batch). Statepoints can be used to analyze tally results as well as
    restart a simulation.

    Attributes
    ----------
    cmfd_on : bool
        Indicate whether CMFD is active
    cmfd_balance : ndarray
        Residual neutron balance for each batch
    cmfd_dominance
        Dominance ratio for each batch
    cmfd_entropy : ndarray
        Shannon entropy of CMFD fission source for each batch
    cmfd_indices : ndarray
        Number of CMFD mesh cells and energy groups. The first three indices
        correspond to the x-, y-, and z- spatial directions and the fourth index
        is the number of energy groups.
    cmfd_srccmp : ndarray
        Root-mean-square difference between OpenMC and CMFD fission source for
        each batch
    cmfd_src : ndarray
        CMFD fission source distribution over all mesh cells and energy groups.
    current_batch : Integral
        Number of batches simulated
    date_and_time : str
        Date and time when simulation began
    entropy : ndarray
        Shannon entropy of fission source at each batch
    gen_per_batch : Integral
        Number of fission generations per batch
    global_tallies : ndarray of compound datatype
        Global tallies for k-effective estimates and leakage. The compound
        datatype has fields 'name', 'sum', 'sum_sq', 'mean', and 'std_dev'.
    k_combined : list
        Combined estimator for k-effective and its uncertainty
    k_col_abs : Real
        Cross-product of collision and absorption estimates of k-effective
    k_col_tra : Real
        Cross-product of collision and tracklength estimates of k-effective
    k_abs_tra : Real
        Cross-product of absorption and tracklength estimates of k-effective
    k_generation : ndarray
        Estimate of k-effective for each batch/generation
    meshes : dict
        Dictionary whose keys are mesh IDs and whose values are Mesh objects
    n_batches : Integral
        Number of batches
    n_inactive : Integral
        Number of inactive batches
    n_particles : Integral
        Number of particles per generation
    n_realizations : Integral
        Number of tally realizations
    path : str
        Working directory for simulation
    run_mode : str
        Simulation run mode, e.g. 'k-eigenvalue'
    seed : Integral
        Pseudorandom number generator seed
    source : ndarray of compound datatype
        Array of source sites. The compound datatype has fields 'wgt', 'xyz',
        'uvw', and 'E' corresponding to the weight, position, direction, and
        energy of the source site.
    source_present : bool
        Indicate whether source sites are present
    tallies : dict
        Dictionary whose keys are tally IDs and whose values are Tally objects
    tallies_present : bool
        Indicate whether user-defined tallies are present
    version: tuple of Integral
        Version of OpenMC
    summary : None or openmc.summary.Summary
        A summary object if the statepoint has been linked with a summary file

    """

    def __init__(self, filename):
        import h5py
        self._f = h5py.File(filename, 'r')

        # Ensure filetype and revision are correct
        try:
            if 'filetype' not in self._f or self._f[
                    'filetype'].value.decode() != 'statepoint':
                raise IOError('{} is not a statepoint file.'.format(filename))
        except AttributeError:
            raise IOError('Could not read statepoint file. This most likely '
                          'means the statepoint file was produced by a different '
                          'version of OpenMC than the one you are using.')
        if self._f['revision'].value != 14:
            raise IOError('Statepoint file has a file revision of {} '
                          'which is not consistent with the revision this '
                          'version of OpenMC expects ({}).'.format(
                              self._f['revision'].value, 14))

        # Set flags for what data has been read
        self._meshes_read = False
        self._tallies_read = False
        self._summary = False
        self._global_tallies = None

    def close(self):
        self._f.close()

    @property
    def cmfd_on(self):
        return self._f['cmfd_on'].value > 0

    @property
    def cmfd_balance(self):
        return self._f['cmfd/cmfd_balance'].value if self.cmfd_on else None

    @property
    def cmfd_dominance(self):
        return self._f['cmfd/cmfd_dominance'].value if self.cmfd_on else None

    @property
    def cmfd_entropy(self):
        return self._f['cmfd/cmfd_entropy'].value if self.cmfd_on else None

    @property
    def cmfd_indices(self):
        return self._f['cmfd/indices'].value if self.cmfd_on else None

    @property
    def cmfd_src(self):
        if self.cmfd_on:
            data = self._f['cmfd/cmfd_src'].value
            return np.reshape(data, tuple(self.cmfd_indices), order='F')
        else:
            return None

    @property
    def cmfd_srccmp(self):
        return self._f['cmfd/cmfd_srccmp'].value if self.cmfd_on else None

    @property
    def current_batch(self):
        return self._f['current_batch'].value

    @property
    def date_and_time(self):
        return self._f['date_and_time'].value.decode()

    @property
    def entropy(self):
        if self.run_mode == 'k-eigenvalue':
            return self._f['entropy'].value
        else:
            return None

    @property
    def gen_per_batch(self):
        if self.run_mode == 'k-eigenvalue':
            return self._f['gen_per_batch'].value
        else:
            return None

    @property
    def global_tallies(self):
        if self._global_tallies is None:
            data = self._f['global_tallies'].value
            gt = np.zeros_like(data, dtype=[
                ('name', 'a14'), ('sum', 'f8'), ('sum_sq', 'f8'),
                ('mean', 'f8'), ('std_dev', 'f8')])
            gt['name'] = ['k-collision', 'k-absorption', 'k-tracklength',
                          'leakage']
            gt['sum'] = data['sum']
            gt['sum_sq'] = data['sum_sq']

            # Calculate mean and sample standard deviation of mean
            n = self.n_realizations
            gt['mean'] = gt['sum']/n
            gt['std_dev'] = np.sqrt((gt['sum_sq']/n - gt['mean']**2)/(n - 1))

            self._global_tallies = gt

        return self._global_tallies

    @property
    def k_cmfd(self):
        if self.cmfd_on:
            return self._f['cmfd/k_cmfd'].value
        else:
            return None

    @property
    def k_generation(self):
        if self.run_mode == 'k-eigenvalue':
            return self._f['k_generation'].value
        else:
            return None

    @property
    def k_combined(self):
        if self.run_mode == 'k-eigenvalue':
            return self._f['k_combined'].value
        else:
            return None

    @property
    def k_col_abs(self):
        if self.run_mode == 'k-eigenvalue':
            return self._f['k_col_abs'].value
        else:
            return None

    @property
    def k_col_tra(self):
        if self.run_mode == 'k-eigenvalue':
            return self._f['k_col_tra'].value
        else:
            return None

    @property
    def k_abs_tra(self):
        if self.run_mode == 'k-eigenvalue':
            return self._f['k_abs_tra'].value
        else:
            return None

    @property
    def meshes(self):
        if not self._meshes_read:
            # Initialize dictionaries for the Meshes
            # Keys     - Mesh IDs
            # Values - Mesh objects
            self._meshes = {}

            # Read the number of Meshes
            n_meshes = self._f['tallies/meshes/n_meshes'].value

            # Read a list of the IDs for each Mesh
            if n_meshes > 0:
                # User-defined Mesh IDs
                mesh_keys = self._f['tallies/meshes/keys'].value
            else:
                mesh_keys = []

            # Build dictionary of Meshes
            base = 'tallies/meshes/mesh '

            # Iterate over all Meshes
            for mesh_key in mesh_keys:
                # Read the mesh type
                mesh_type = self._f['{0}{1}/type'.format(base, mesh_key)].value.decode()

                # Read the mesh dimensions, lower-left coordinates,
                # upper-right coordinates, and width of each mesh cell
                dimension = self._f['{0}{1}/dimension'.format(base, mesh_key)].value
                lower_left = self._f['{0}{1}/lower_left'.format(base, mesh_key)].value
                upper_right = self._f['{0}{1}/upper_right'.format(base, mesh_key)].value
                width = self._f['{0}{1}/width'.format(base, mesh_key)].value

                # Create the Mesh and assign properties to it
                mesh = openmc.Mesh(mesh_key)
                mesh.dimension = dimension
                mesh.width = width
                mesh.lower_left = lower_left
                mesh.upper_right = upper_right
                mesh.type = mesh_type

                # Add mesh to the global dictionary of all Meshes
                self._meshes[mesh_key] = mesh

            self._meshes_read = True

        return self._meshes

    @property
    def n_batches(self):
        return self._f['n_batches'].value

    @property
    def n_inactive(self):
        if self.run_mode == 'k-eigenvalue':
            return self._f['n_inactive'].value
        else:
            return None

    @property
    def n_particles(self):
        return self._f['n_particles'].value

    @property
    def n_realizations(self):
        return self._f['n_realizations'].value

    @property
    def path(self):
        return self._f['path'].value.decode()

    @property
    def run_mode(self):
        return self._f['run_mode'].value.decode()

    @property
    def seed(self):
        return self._f['seed'].value

    @property
    def source(self):
        return self._f['source_bank'].value if self.source_present else None

    @property
    def source_present(self):
        return self._f['source_present'].value > 0

    @property
    def tallies(self):
        if not self._tallies_read:
            # Initialize dictionary for tallies
            self._tallies = {}

            # Read the number of tallies
            n_tallies = self._f['tallies/n_tallies'].value

            # Read a list of the IDs for each Tally
            if n_tallies > 0:
                # OpenMC Tally IDs (redefined internally from user definitions)
                tally_keys = self._f['tallies/keys'].value
            else:
                tally_keys = []

            base = 'tallies/tally '

            # Iterate over all Tallies
            for tally_key in tally_keys:

                # Read the Tally size specifications
                n_realizations = self._f['{0}{1}/n_realizations'.format(base, tally_key)].value

                # Create Tally object and assign basic properties
                tally = openmc.Tally(tally_id=tally_key)
                tally._sp_filename = self._f.filename
                tally.estimator = self._f['{0}{1}/estimator'.format(
                    base, tally_key)].value.decode()
                tally.num_realizations = n_realizations

                # Read the number of Filters
                n_filters = self._f['{0}{1}/n_filters'.format(base, tally_key)].value

                subbase = '{0}{1}/filter '.format(base, tally_key)

                # Initialize all Filters
                for j in range(1, n_filters+1):

                    # Read the Filter type
                    filter_type = self._f['{0}{1}/type'.format(subbase, j)].value.decode()

                    # Read the Filter offset
                    offset = self._f['{0}{1}/offset'.format(subbase, j)].value

                    n_bins = self._f['{0}{1}/n_bins'.format(subbase, j)].value

                    # Read the bin values
                    bins = self._f['{0}{1}/bins'.format(subbase, j)].value

                    # Create Filter object
                    filter = openmc.Filter(filter_type, bins)
                    filter.offset = offset
                    filter.num_bins = n_bins

                    if filter_type == 'mesh':
                        mesh_ids = self._f['tallies/meshes/ids'].value
                        mesh_keys = self._f['tallies/meshes/keys'].value

                        key = mesh_keys[mesh_ids == bins][0]
                        filter.mesh = self.meshes[key]

                    # Add Filter to the Tally
                    tally.add_filter(filter)

                # Read Nuclide bins
                nuclide_names = self._f['{0}{1}/nuclides'.format(base, tally_key)].value

                # Add all Nuclides to the Tally
                for name in nuclide_names:
                    nuclide = openmc.Nuclide(name.decode().strip())
                    tally.add_nuclide(nuclide)

                # Read score bins
                n_score_bins = self._f['{0}{1}/n_score_bins'.format(base, tally_key)].value

                tally.num_score_bins = n_score_bins

                scores = self._f['{0}{1}/score_bins'.format(
                    base, tally_key)].value
                n_user_scores = self._f['{0}{1}/n_user_score_bins'
                                        .format(base, tally_key)].value

                # Compute and set the filter strides
                for i in range(n_filters):
                    filter = tally.filters[i]
                    filter.stride = n_score_bins * len(nuclide_names)

                    for j in range(i+1, n_filters):
                        filter.stride *= tally.filters[j].num_bins

                # Read scattering moment order strings (e.g., P3, Y-1,2, etc.)
                moments = self._f['{0}{1}/moment_orders'.format(
                    base, tally_key)].value

                # Add the scores to the Tally
                for j, score in enumerate(scores):
                    score = score.decode()

                    # If this is a moment, use generic moment order
                    pattern = r'-n$|-pn$|-yn$'
                    score = re.sub(pattern, '-' + moments[j].decode(), score)

                    tally.add_score(score)

                # Add Tally to the global dictionary of all Tallies
                self._tallies[tally_key] = tally

            self._tallies_read = True

        return self._tallies

    @property
    def tallies_present(self):
        return self._f['tallies/tallies_present'].value

    @property
    def version(self):
        return (self._f['version_major'].value,
                self._f['version_minor'].value,
                self._f['version_release'].value)

    @property
    def summary(self):
        return self._summary

    @property
    def with_summary(self):
        return False if self.summary is None else True

    def get_tally(self, scores=[], filters=[], nuclides=[],
                  name=None, id=None, estimator=None):
        """Finds and returns a Tally object with certain properties.

        This routine searches the list of Tallies and returns the first Tally
        found which satisfies all of the input parameters.
        NOTE: The input parameters do not need to match the complete Tally
        specification and may only represent a subset of the Tally's properties.

        Parameters
        ----------
        scores : list, optional
            A list of one or more score strings (default is []).
        filters : list, optional
            A list of Filter objects (default is []).
        nuclides : list, optional
            A list of Nuclide objects (default is []).
        name : str, optional
            The name specified for the Tally (default is None).
        id : Integral, optional
            The id specified for the Tally (default is None).
        estimator: str, optional
            The type of estimator ('tracklength', 'analog'; default is None).

        Returns
        -------
        tally : Tally
            A tally matching the specified criteria

        Raises
        ------
        LookupError
            If a Tally meeting all of the input parameters cannot be found in
            the statepoint.

        """

        tally = None

        # Iterate over all tallies to find the appropriate one
        for tally_id, test_tally in self.tallies.items():

            # Determine if Tally has queried name
            if name and name != test_tally.name:
                continue

            # Determine if Tally has queried id
            if id and id != test_tally.id:
                continue

            # Determine if Tally has queried estimator
            if estimator and not estimator == test_tally.estimator:
                continue

            # Determine if Tally has the queried score(s)
            if scores:
                contains_scores = True

                # Iterate over the scores requested by the user
                for score in scores:
                    if score not in test_tally.scores:
                        contains_scores = False
                        break

                if not contains_scores:
                    continue

            # Determine if Tally has the queried Filter(s)
            if filters:
                contains_filters = True

                # Iterate over the Filters requested by the user
                for filter in filters:
                    contains_filters = False

                    # Test if requested filter is a subset of any of the test
                    # tally's filters and if so continue to next filter
                    for test_filter in test_tally.filters:
                        if test_filter.is_subset(filter):
                            contains_filters = True
                            break

                    if not contains_filters:
                        break

                if not contains_filters:
                    continue

            # Determine if Tally has the queried Nuclide(s)
            if nuclides:
                contains_nuclides = True

                # Iterate over the Nuclides requested by the user
                for nuclide in nuclides:
                    if nuclide not in test_tally.nuclides:
                        contains_nuclides = False
                        break

                if not contains_nuclides:
                    continue

            # If the current Tally met user's request, break loop and return it
            tally = test_tally
            break

        # If we did not find the Tally, return an error message
        if tally is None:
            raise LookupError('Unable to get Tally')

        return tally

    def link_with_summary(self, summary):
        """Links Tallies and Filters with Summary model information.

        This routine retrieves model information (materials, geometry) from a
        Summary object populated with an HDF5 'summary.h5' file and inserts it
        into the Tally objects. This can be helpful when viewing and
        manipulating large scale Tally data. Note that it is necessary to link
        against a summary to populate the Tallies with any user-specified "name"
        XML tags.

        Parameters
        ----------
        summary : Summary
             A Summary object.

        Raises
        ------
        ValueError
            An error when the argument passed to the 'summary' parameter is not
            an openmc.Summary object.

        """

        if not isinstance(summary, openmc.summary.Summary):
            msg = 'Unable to link statepoint with "{0}" which ' \
                  'is not a Summary object'.format(summary)
            raise ValueError(msg)

        for tally_id, tally in self.tallies.items():
            # Get the Tally name from the summary file
            tally.name = summary.tallies[tally_id].name
            tally.with_summary = True

            for filter in tally.filters:
                if filter.type == 'surface':
                    surface_ids = []
                    for bin in filter.bins:
                        surface_ids.append(summary.surfaces[bin].id)
                    filter.bins = surface_ids

                if filter.type in ['cell', 'distribcell']:
                    distribcell_ids = []
                    for bin in filter.bins:
                        distribcell_ids.append(summary.cells[bin].id)
                    filter.bins = distribcell_ids

                if filter.type == 'universe':
                    universe_ids = []
                    for bin in filter.bins:
                        universe_ids.append(summary.universes[bin].id)
                    filter.bins = universe_ids

                if filter.type == 'material':
                    material_ids = []
                    for bin in filter.bins:
                        material_ids.append(summary.materials[bin].id)
                    filter.bins = material_ids

        self._summary = summary
