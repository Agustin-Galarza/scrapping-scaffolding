from argparse import ArgumentParser
from pathlib import Path

from . import Cyberdrop


def prepare_parser() -> ArgumentParser:
    parser = ArgumentParser()

    parser.add_argument('-u','--upload',type=str,help='Uploads a directory to the server')
    parser.add_argument('-a','--album',type=str,default=None,help='Album to upload the files to')

    parser.add_argument('--list-albums',action='store_true',help='Prints the existing albums and returns')
    parser.add_argument('--list-files',action='store_true',help='Prints the uploaded files and returns')
    parser.add_argument('--max-files',type=int,default=25,help='Max amount of files to print')

    return parser

parser = prepare_parser()
args = parser.parse_args()

cd = Cyberdrop()

if args.list_albums:
    print(*cd.get_albums())
    exit()

if args.list_files:
    print(*cd.get_uploaded_files(args.max_files))
    exit()

if args.upload is not None:
    upload_path = Path(args.upload)
    
    print(f'Uploading {args.upload} to the server...')
    cd.upload_dir(upload_path, args.album)
    print('Upload finished')
    exit()

parser.print_help()

