import h5py
import awkward as ak
import os
import argparse
from tqdm import tqdm

# Argument Parsing
parser = argparse.ArgumentParser(description='Convert top benchmark h5 datasets to ROOT/awkd')
parser.add_argument('-i', '--inputdir', required=True, help='Directory that contains the input h5 file.')
parser.add_argument('-c', '--condition', default='all', choices=['train', 'val', 'test', 'all'], help='Create dataset for train/test/val/all.')
parser.add_argument('-m', '--mode', default='uproot', choices=['awkd', 'uproot', 'ROOT'], help='Mode to write ROOT files')
parser.add_argument('--max-event-size', type=int, default=100000, help='Maximum event size per output file.')
args = parser.parse_args()

def store_file_uproot(res_array_2d, res_array_1d, outpath):
    import uproot
    def _check_uproot_version(uproot):
        v = uproot.__version__.split('.')
        v = int(v[0])*10000 + int(v[1])*100 + int(v[2])
        assert v >= 40104, "Uproot version should be >= 4.1.4 for the stable uproot-writing feature"
    _check_uproot_version(uproot)
    outpath += '.root'
    print('Saving to file', outpath, '...')
    ak_array2d = ak.from_iter(res_array_2d)
    ak_array1d = ak.from_iter(res_array_1d)
    if not os.path.exists(os.path.dirname(outpath)):
        os.makedirs(os.path.dirname(outpath))
    with uproot.recreate(outpath, compression=uproot.LZ4(4)) as fw:
        print('2D array contents:', ak_array2d)
        print('1D array contents:', ak_array1d)
        try:
            fields_2d = ak.fields(ak_array2d)
            fields_1d = ak.fields(ak_array1d)
            print('2D array fields:', fields_2d)
            print('1D array fields:', fields_1d)
            if not fields_2d or not fields_1d:
                print("Error: One or more fields are empty. Check your input data.")
            fw['Events'] = {'Part': ak.zip({k:ak_array2d[k] for k in fields_2d}), **{k:ak_array1d[k] for k in fields_1d if k != 'nPart'}}
            fw['Events'].title = 'Events'
        except Exception as e:
            print(f"Error while saving to ROOT: {e}")

def convert(input_files, output_file, store_file_func):
    varlist_2d = ['fjet_clus_E', 'fjet_clus_eta', 'fjet_clus_phi', 'fjet_clus_pt']
    varlist_1d = ['fjet_eta', 'fjet_phi', 'fjet_pt', 'fjet_m', 'labels', 'weights']
    idx, ifile = 0, 0
    res_array_2d, res_array_1d = [], []
    for filename in input_files:
        print('Reading datasets from:', filename, '...')
        with h5py.File(filename, 'r') as f:
            # Print all available keys
            print("Available keys in HDF5 file:", list(f.keys()))
            datasets = {key: f[key][:] for key in f.keys()}
        
        # Debug print to check contents
        for key in datasets:
            print(f"Dataset {key} has shape {datasets[key].shape} and dtype {datasets[key].dtype}")

        if not any(k in datasets for k in varlist_2d + varlist_1d):
            print("None of the required datasets found in the HDF5 file.")
            continue

        print('Processing events ...')
        isfirst = True
        for i in tqdm(range(len(datasets.get('fjet_eta', [])))):
            if idx >= args.max_event_size:
                store_file_func(res_array_2d, res_array_1d, os.path.join(args.inputdir, 'prep', f'{output_file}_{ifile}'))
                del res_array_2d, res_array_1d
                res_array_2d, res_array_1d = [], []
                ifile += 1
                idx = 0

            res = {k: datasets[k][i] for k in varlist_2d if k in datasets}
            res.update({k: datasets[k][i] for k in varlist_1d if k in datasets})
            res_array_2d.append({k: res[k] for k in varlist_2d if k in res})
            res_array_1d.append({k: res[k] for k in varlist_1d if k in res})

            print('2D array content:', res_array_2d[-1])
            print('1D array content:', res_array_1d[-1])

            if isfirst:
                print(res)
                isfirst = False

            idx += 1

    store_file_func(res_array_2d, res_array_1d, os.path.join(args.inputdir, 'prep', f'{output_file}_{ifile}'))

if __name__ == '__main__':
    store_file_func = store_file_uproot if args.mode == 'uproot' else None
    if args.condition == 'test':
        convert(input_files=['test.h5'], output_file='top_test', store_file_func=store_file_func)
    elif args.condition == 'all':
        convert(input_files=['test.h5'], output_file='top_test', store_file_func=store_file_func)

