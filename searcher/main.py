from argparse import ArgumentParser
from searcher import BunkrSearcher, download_results, load_config
from searcher.download import BunkrDownloader
from pathlib import Path

def prepare_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument(
        'query',
        type=str,
        help='The query string to search in the bunkr page'
    )

    parser.add_argument('-c','--config-file',type=str,default='./config/searcher.config.json',help='Defines the path for the config file')

    parser.add_argument('--omit-results',action='store_true',help='When set avoid printing the results from the search to the console')
    parser.add_argument('-l','--load-pages',type=int,default=1,help='Defines the amount of pages from the query result to load into the search result.')

    parser.add_argument('-d','--download',action='store_true',help='When set, downloads the results from the search, up to [max-size]')
    parser.add_argument('-o','--output-dir',type=str,default='./output',help='Path to the destination directory to save the downloaded results')
    parser.add_argument('--content-dir',type=str,help='Path to the downloaded content. This path must be relative to the output directory path.')
    parser.add_argument('-M','--max-total-size',type=str,help='Max total size to download (1 KB = 1024 B)')
    parser.add_argument('-m','--max-album-size',type=str,help='Max size for an album to download it (1 KB = 1024 B)')
    parser.add_argument('-f','--filter-download',type=str,help='When downloading, filter the downloaded albums by this string as a regular expression.')
    parser.add_argument('--merge-expr',type=str,default=None,help='Regular expression to extract the name of the album from the url. This is used to merge the results into a single download.')

    parser.add_argument('-v','--verbose',action='store_true',help='Set verbose mode')
    return parser

def main():
    args = prepare_parser().parse_args()

    config = load_config(Path(args.config_file))
    searcher = BunkrSearcher(config)
    print(f'Searching on Bunkr site for query {args.query}')
    result = searcher.search(args.query, max_loaded_pages=args.load_pages)
    print('Search successful!')
    if not args.omit_results and not args.download:
        print(result)
    
    if args.download:
        downloader = BunkrDownloader()
        downloader.download(
            result, 
            config.downloads if args.output_dir is None else Path(args.output_dir), 
            Path(args.content_dir) if args.content_dir is not None else None, 
            args.max_total_size, 
            args.max_album_size, 
            args.filter_download, 
            args.merge_expr,
            args.verbose
            )

if __name__ == '__main__':
    main()

    