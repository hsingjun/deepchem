"""
Utility functions to load datasets.
"""
__author__ = "Bharath Ramsundar"
__copyright__ = "Copyright 2015, Stanford University"
__license__ = "LGPL"

def load_descriptors(paths, descriptor_dir_name="descriptors"):
  """Load dataset descriptors and return.

  Returns a dictionary that maps mol_id to descriptors. (Descriptors are
  taken from rdkit.Chem and consist of basic physiochemical property
  values.

  Parameters
  ----------
  paths: list
    List of strings.
  """
  descriptor_dict = {}
  for dataset_path in paths:
    pickle_dir = os.path.join(dataset_path, descriptor_dir_name)
    for pickle_file in os.listdir(pickle_dir):
      with gzip.open(os.path.join(pickle_dir, pickle_file), "rb") as f:
        contents = pickle.load(f)
        all_smiles, descriptors = (contents["smiles"], contents["features"])
        for mol in range(len(all_smiles)):
          n_descriptors = len(descriptors[mol])
          bad_sets = [1, 28, 55, 68, 71, 72, 81, 83, 84, 85, 86, 87, 88,
          123, 124, 129, 137, 142, 143, 144, 146, 148, 149, 150, 156, 157,
          159, 160, 161, 164, 169, 170, 171, 173, 178, 179, 183, 190, 192]
          descriptor_dict[all_smiles[mol]] = np.array(
              [descriptors[mol][index] for index in range(n_descriptors) if
                  index not in bad_sets])
  return descriptor_dict

def load_molecules(paths, dir_name="circular-scaffold-smiles"):
  """Load dataset fingerprints and return fingerprints.

  Returns a dictionary that maps smiles strings to dicts that contain
  fingerprints, smiles strings, scaffolds, mol_ids.

  Parameters
  ----------
  paths: list
    List of strings.
  """
  molecules = {}
  for dataset_path in paths:
    pickle_dir = os.path.join(dataset_path, dir_name)
    for pickle_file in os.listdir(pickle_dir):
      with gzip.open(os.path.join(pickle_dir, pickle_file), "rb") as f:
        contents = pickle.load(f)
        smiles, fingerprints, scaffolds, mol_ids = (
            contents["smiles"], contents["features"],
            contents["scaffolds"], contents["mol_id"])
        for mol in range(len(contents["smiles"])):
          molecules[smiles[mol]] = {"fingerprint": fingerprints[mol],
                                    "scaffold": scaffolds[mol],
                                    "mol_id": mol_ids[mol]}
  return molecules 

def get_target_names(paths, target_dir_name="targets"):
  """Get names of targets in provided collections.

  Parameters
  ----------
  paths: list 
    List of paths to base directory.
  """
  target_names = []
  for dataset_path in paths:
    target_dir = os.path.join(dataset_path, target_dir_name)
    target_names += [target_pickle.split(".")[0]
        for target_pickle in os.listdir(target_dir)
        if "pkl.gz" in target_pickle]
  return target_names

def load_assays(paths, target_dir_name="targets"):
  """Load regression dataset labels from assays.

  Returns a dictionary that maps smiles strings to label vectors.

  TODO(rbharath): Simplify this function to only support the new pickle format.

  Parameters
  ----------
  paths: list 
    List of paths to base directory.
  target_dir_name: string
    Name of subdirectory containing assay data.
  """
  datapoints = {}
  # Compute target names
  target_names = get_target_names(paths, target_dir_name)
  for dataset_path in paths:
    target_dir = os.path.join(dataset_path, target_dir_name)
    for target_pickle in os.listdir(target_dir):
      if "pkl.gz" not in target_pickle:
        continue
      target_name = target_pickle.split(".")[0]
      with gzip.open(os.path.join(target_dir, target_pickle), "rb") as f:
        contents = pickle.load(f)
        if "potency" in contents:
          items = zip(contents["smiles"], contents["potency"])
        elif "targets" in contents:
          items = zip(contents["smiles"], contents["targets"])
        else:
          raise ValueError("Must contain either potency or targets field.")
        for mol, potency in items:
          # TODO(rbharath): Get a less kludgey answer
          # TODO(rbharath): There is some amount of duplicate collisions
          # due to choice of smiles generation. Look into this more
          # carefully and see if the underlying issues are fundamental..
          try:
            if potency is None or np.isnan(potency):
              continue
          except TypeError:
            continue
          if mol not in datapoints:
            datapoints[mol] = {}
            # Ensure that each target has some entry in dict.
            for name in target_names:
              # Set all targets to invalid for now.
              datapoints[mol][name] = -1
          datapoints[mol][target_name] = potency 
  return datapoints

def load_datasets(paths, datatype="vs", **load_args):
  """Dispatches to correct loader depending on type of data."""
  if datatype == "vs":
    return load_vs_datasets(paths, **load_args)
  elif datatype == "pdbbind":
    return load_pdbbind_datasets(paths, **load_args)
  else:
    raise ValueError("Unsupported datatype.")

def load_pdbbind_datasets(pdbbind_paths):
  """Load pdbbind datasets.

  Parameters
  ----------
  pdbbind_path: list 
    List of Pdbbind data files.
  """
  data = []
  for pdbbind_path in pdbbind_paths:
    with open(pdbbind_path, "rb") as csvfile:
      reader = csv.reader(csvfile)
      for row_ind, row in enumerate(reader):
        if row_ind == 0:
          continue
        data.append({
          "label": row[0],
          "features": row[1],
        })
  df = pd.DataFrame(data)
  print df.shape
  return df

def load_vs_datasets(paths, target_dir_name="targets",
    fingerprint_dir_name="circular-scaffold-smiles",
    descriptor_dir_name="descriptors",
    add_descriptors=False):
  """Load both labels and fingerprints.

  Returns a dictionary that maps smiles to pairs of (fingerprint, labels)
  where labels is itself a dict that maps target-names to labels.

  Parameters
  ----------
  paths: string or list
    Paths to base directory.
  """
  data = {}
  molecules = load_molecules(paths, fingerprint_dir_name)
  labels = load_assays(paths, target_dir_name)
  if add_descriptors:
    descriptors = load_descriptors(paths, descriptor_dir_name)
  # TODO(rbharath): Why are there fewer descriptors than labels at times?
  # What accounts for the descrepency. Please investigate.
  for ind, smiles in enumerate(molecules):
    if smiles not in labels or (add_descriptors and smiles not in descriptors):
      continue
    mol = molecules[smiles]
    if add_descriptors:
      data[smiles] = {"fingerprint": mol["fingerprint"],
                      "scaffold": mol["scaffold"],
                      "labels": labels[smiles],
                      "descriptors": descriptors[smiles]}
    else:
      data[smiles] = {"fingerprint": mol["fingerprint"],
                      "scaffold": mol["scaffold"],
                      "labels": labels[smiles]}
  return data

def load_and_transform_dataset(paths, task_transforms, desc_transforms={},
    labels_endpoint="labels", descriptors_endpoint="descriptors",
    add_descriptors=False):
  """Transform data labels as specified

  Parameters
  ----------
  paths: list 
    List of paths to Google vs datasets. 
  task_transforms: dict 
    dict mapping target names to list of label transforms. Each list
    element must be "max-val", "log", "normalize". The transformations are
    performed in the order specified. An empty list
    corresponds to no transformations. Only for regression outputs.
  desc_transforms: dict
    dict mapping descriptor number to transform. Each transform must be
    either None, "log", "normalize", or "log-normalize"
  add_descriptors: bool
    Add descriptor prediction as extra task.
  """
  dataset = load_datasets(paths, add_descriptors=add_descriptors)
  X, y, W = transform_outputs(dataset, task_transforms,
      desc_transforms=desc_transforms, add_descriptors=add_descriptors)
  trans_data = {}
  sorted_smiles = sorted(dataset.keys())
  sorted_targets = sorted(task_transforms.keys())
  for s_index, smiles in enumerate(sorted_smiles):
    datapoint = dataset[smiles]
    labels = {}
    for t_index, target in enumerate(sorted_targets):
      if W[s_index][t_index] == 0:
        labels[target] = -1
      else:
        labels[target] = y[s_index][t_index]
    datapoint[labels_endpoint] = labels
    if add_descriptors:
      # All non-target endpoints are descriptors
      datapoint[descriptors_endpoint] = y[s_index][len(sorted_targets):]
    trans_data[smiles] = datapoint 
  return trans_data