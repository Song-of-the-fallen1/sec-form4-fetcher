"""
SEC Form 4 Fetcher
Fetches and parses insider transaction filings from SEC EDGAR.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import time

class Form4Fetcher:
    """Fetch and parse SEC Form 4 filings."""
    
    def __init__(self):
        self.base_url = "https://www.sec.gov"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate'
        }
        self.namespace = {
            'ns': 'http://www.sec.gov/edgar/form4'
        }
    
    def get_recent_filings(self, days_back: int = 7) -> List[Dict]:
        """
        Get Form 4 filings from the last N days using EDGAR RSS feed.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of filing metadata
        """
        # EDGAR RSS feed URL
        rss_url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type=4&company=&dateb=&owner=include&start=0&count=100&output=atom"
        
        try:
            response = requests.get(rss_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # Parse RSS feed (simplified - production would use feedparser)
            filings = []
            
            # For demonstration, we'll return mock data
            # In production, you would parse the actual RSS XML
            filings.append({
                'cik': '0001326801',
                'company': 'Palantir Technologies Inc.',
                'filing_date': datetime.now().strftime('%Y-%m-%d'),
                'accession_number': '0000000-24-000001',
                'url': f"{self.base_url}/Archives/edgar/data/0001326801/0000000-24-000001-index.htm"
            })
            
            return filings
            
        except Exception as e:
            print(f"Error fetching recent filings: {e}")
            return []
    
    def fetch_filing(self, cik: str, accession_number: str) -> Optional[str]:
        """
        Fetch a specific Form 4 filing XML.
        
        Args:
            cik: Company CIK number (10 digits with leading zeros)
            accession_number: SEC accession number
            
        Returns:
            XML content as string or None if not found
        """
        # Format CIK with leading zeros to 10 digits
        cik_padded = cik.zfill(10)
        
        # Construct URL
        url = f"{self.base_url}/Archives/edgar/data/{cik_padded}/{accession_number.replace('-', '')}/{accession_number}-index.htm"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching filing {accession_number}: {e}")
            return None
    
    def parse_filing_xml(self, xml_content: str) -> Dict:
        """
        Parse Form 4 XML to extract transaction details.
        
        Args:
            xml_content: XML string from SEC EDGAR
            
        Returns:
            Structured transaction data
        """
        try:
            root = ET.fromstring(xml_content)
            
            # Extract reporting owner
            reporting_owner = {}
            owner_elem = root.find('.//ns:reportingOwner', self.namespace)
            if owner_elem is not None:
                name_elem = owner_elem.find('.//ns:reportingOwnerName', self.namespace)
                if name_elem is not None:
                    reporting_owner['name'] = name_elem.text
                
                relationship = owner_elem.find('.//ns:reportingOwnerRelationship', self.namespace)
                if relationship is not None:
                    officer_elem = relationship.find('.//ns:isOfficer', self.namespace)
                    director_elem = relationship.find('.//ns:isDirector', self.namespace)
                    ten_percent_elem = relationship.find('.//ns:isTenPercentOwner', self.namespace)
                    
                    reporting_owner['is_officer'] = officer_elem is not None and officer_elem.text == '1'
                    reporting_owner['is_director'] = director_elem is not None and director_elem.text == '1'
                    reporting_owner['is_ten_percent_owner'] = ten_percent_elem is not None and ten_percent_elem.text == '1'
                    
                    title_elem = relationship.find('.//ns:officerTitle', self.namespace)
                    if title_elem is not None:
                        reporting_owner['title'] = title_elem.text
            
            # Extract non-derivative transactions
            transactions = []
            non_derivative = root.find('.//ns:nonDerivativeTable', self.namespace)
            if non_derivative is not None:
                for transaction in non_derivative.findall('.//ns:nonDerivativeTransaction', self.namespace):
                    tx = self._parse_transaction(transaction)
                    if tx:
                        transactions.append(tx)
            
            return {
                'reporting_owner': reporting_owner,
                'transactions': transactions,
                'parsed_at': datetime.now().isoformat()
            }
            
        except ET.ParseError as e:
            print(f"XML parsing error: {e}")
            return {'error': 'Failed to parse XML', 'transactions': []}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {'error': str(e), 'transactions': []}
    
    def _parse_transaction(self, transaction_elem) -> Optional[Dict]:
        """Parse a single transaction element."""
        try:
            # Transaction date
            date_elem = transaction_elem.find('.//ns:transactionDate', self.namespace)
            if date_elem is None:
                return None
            
            # Transaction coding
            code_elem = transaction_elem.find('.//ns:transactionCode', self.namespace)
            transaction_code = code_elem.text if code_elem is not None else None
            
            # Only track open market purchases (P) and sales (S)
            if transaction_code not in ['P', 'S']:
                return None
            
            # Shares
            shares_elem = transaction_elem.find('.//ns:transactionShares', self.namespace)
            shares = None
            if shares_elem is not None:
                value_elem = shares_elem.find('.//ns:value', self.namespace)
                if value_elem is not None:
                    shares = int(value_elem.text)
            
            # Price
            price_elem = transaction_elem.find('.//ns:transactionPricePerShare', self.namespace)
            price = None
            if price_elem is not None:
                value_elem = price_elem.find('.//ns:value', self.namespace)
                if value_elem is not None:
                    price = float(value_elem.text)
            
            # Shares owned after transaction
            owned_elem = transaction_elem.find('.//ns:sharesOwnedFollowingTransaction', self.namespace)
            shares_owned = None
            if owned_elem is not None:
                value_elem = owned_elem.find('.//ns:value', self.namespace)
                if value_elem is not None:
                    shares_owned = int(value_elem.text)
            
            return {
                'transaction_code': transaction_code,
                'transaction_type': 'BUY' if transaction_code == 'P' else 'SELL',
                'transaction_date': date_elem.text,
                'shares': shares,
                'price_per_share': price,
                'total_value': shares * price if shares and price else None,
                'shares_owned_after': shares_owned
            }
            
        except Exception as e:
            print(f"Error parsing transaction: {e}")
            return None


# Example usage
if __name__ == "__main__":
    fetcher = Form4Fetcher()
    
    # Get recent filings
    recent = fetcher.get_recent_filings(days_back=7)
    print(f"Found {len(recent)} recent filings")
    
   
    
    parsed = fetcher.parse_filing_xml(mock_xml)
    print(json.dumps(parsed, indent=2))
