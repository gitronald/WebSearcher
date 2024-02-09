""" Collect HTML for individual results from a SERP
"""

import time
import requests
from . import utils
from . import webutils as wu


def check_valid_url(result): 
    """Check if result has url and url is in a valid format"""
    if 'url' in result:
        return True if result['url'].startswith('http') else False
    else:
        return False


def scrape_results_html(results, serp_id, log, headers, ssh_tunnel, 
                        save_dir='.', append_to=''):
    """Scrape and save all unique, non-internal URLs parsed from the SERP
    
    Args:
        save_dir (str, optional): Save results html as `save_dir/results_html/{serp_id}.json`
        append_to (str, optional): Append results html to this file path
    """

    results_html = [] 
    if not results:
        log.info(f'No results to scrape for serp_id {serp_id}')
    else:

        results_wurl = [r for r in results if check_valid_url(r)]
        
        if results_wurl:

            # Prepare session
            keep_headers = ['User-Agent']
            headers = {k:v for k,v in headers.items() if k in keep_headers}
            if ssh_tunnel:
                result_sesh = wu.start_sesh(headers=headers, proxy_port=ssh_tunnel.port)
            else:
                result_sesh = wu.start_sesh(headers=headers)

            # Get all unique result urls
            result_urls = []
            unique_urls = set()
            for result in results_wurl:
                # If the result has a url and we haven't seen it yet
                if result['url'] and result['url'] not in unique_urls:
                    # Take a subset of the keys
                    keep_keys = {'serp_id', 'serp_rank', 'url'}
                    res = {k:v for k,v in result.items() if k in keep_keys} 
                    result_urls.append(res)
                    unique_urls.add(result['url'])
                
            # Scrape results HTML
            for result in result_urls:
                result = scrape_result_html(result_sesh, result, log, ssh_tunnel)
                results_html.append(result)

            # Save results HTML
            if append_to:
                # Append to aggregate file
                utils.write_lines(results_html, append_to)
            else:
                # Save new SERP-specific file
                fp = os.path.join(save_dir, 'results_html', f'{serp_id}.json')
                utils.write_lines(results_html, fp)


def scrape_result_html(result_sesh, result, log, ssh_tunnel):
        resid = f"{result['serp_id']} | {result['url']}"
    
        try:
            r = result_sesh.get(result['url'], timeout=15)
            result['html'] = r.content.decode('utf-8', 'ignore')

        except requests.exceptions.TooManyRedirects:
            result['html'] = 'error_redirects'
            log.exception(f"Results | RedirectsErr | {resid}")

        except requests.exceptions.Timeout:
            result['html'] = 'error_timeout'
            log.exception(f"Results | TimeoutErr | {resid}")

        except requests.exceptions.ConnectionError:
            result['html'] = 'error_connection'
            log.exception(f"Results | ConnectionErr | {resid}")

            # SSH Tunnel may have died, reset SSH session
            if ssh_tunnel:
                ssh_tunnel.tunnel.kill()
                ssh_tunnel.open_tunnel()
                log.info('Results | Restarted SSH tunnel')
                time.sleep(10) # Allow time to establish connection

        except Exception:
            result['html'] = 'error_unknown'
            log.exception(f"Results | Collection Error | {resid}")
