# src/session/redis_session_manager_enhanced.py
"""
Enhanced Redis Session Manager with Comprehensive Calculation Caching.

Caches all astrological calculations:
- Birth chart (D1)
- Divisional charts (D9, D10, etc.)
- Dasha periods (all levels)
- Transit data
- Ayanamsa
- Planet positions
- House positions

Cache Strategy:
- Check cache first (fast)
- Calculate if missing (slow)
- Store result (for next time)
"""

import json
import redis
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class CalculationCache:
    """Metadata about what's been calculated."""
    has_d1_chart: bool = False
    has_d9_chart: bool = False
    has_d10_chart: bool = False
    has_dasha_data: bool = False
    has_transit_data: bool = False
    has_ayanamsa: bool = False
    last_calculated: Optional[str] = None


class EnhancedRedisSessionManager:
    """
    Enhanced session manager with comprehensive calculation caching.
    
    Key Structure:
    - session:{user_id}:user_profile       → User data (24h)
    - session:{user_id}:conversation       → Chat history (24h)
    - session:{user_id}:metadata           → Session metadata (24h)
    
    Calculation Cache (30 days - birth data doesn't change):
    - session:{user_id}:calculations:d1_chart        → D1 birth chart
    - session:{user_id}:calculations:d9_chart        → D9 navamsa
    - session:{user_id}:calculations:d10_chart       → D10 dasamsa
    - session:{user_id}:calculations:d12_chart       → D12 dwadasamsa
    - session:{user_id}:calculations:d16_chart       → D16 shodasamsa
    - session:{user_id}:calculations:d20_chart       → D20 vimsamsa
    - session:{user_id}:calculations:d24_chart       → D24 chaturvimsamsa
    - session:{user_id}:calculations:d27_chart       → D27 nakshatramsa
    - session:{user_id}:calculations:d30_chart       → D30 trimsamsa
    - session:{user_id}:calculations:d40_chart       → D40 khavedamsa
    - session:{user_id}:calculations:d45_chart       → D45 akshavedamsa
    - session:{user_id}:calculations:d60_chart       → D60 shashtiamsa
    - session:{user_id}:calculations:dasha_data      → Vimshottari dasha
    - session:{user_id}:calculations:ayanamsa        → Ayanamsa value
    - session:{user_id}:calculations:planet_positions → Planet positions
    - session:{user_id}:calculations:house_positions  → House cusps
    
    Transit Cache (2 hours - changes frequently):
    - session:{user_id}:transits:current             → Current transits
    """
    
    # TTL values in seconds
    TTL_USER_PROFILE = 86400           # 24 hours
    TTL_CONVERSATION = 86400            # 24 hours
    TTL_METADATA = 86400                # 24 hours
    TTL_CALCULATIONS = 2592000          # 30 days (birth data doesn't change)
    TTL_TRANSITS = 7200                 # 2 hours (transits change)
    
    # Supported divisional charts
    DIVISIONAL_CHARTS = ['d1', 'd9', 'd10', 'd12', 'd16', 'd20', 'd24', 'd27', 'd30', 'd40', 'd45', 'd60']
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, **redis_kwargs):
        """
        Initialize enhanced Redis session manager.
        
        Args:
            redis_client: Existing Redis client, or None to create new
            **redis_kwargs: Redis connection parameters
        """
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=redis_kwargs.get('host', 'localhost'),
                port=redis_kwargs.get('port', 6379),
                db=redis_kwargs.get('db', 0),
                password=redis_kwargs.get('password', None),
                decode_responses=True
            )
        
        # Test connection
        try:
            self.redis.ping()
            print("[SESSION] Redis connection established")
        except redis.ConnectionError as e:
            print(f"[SESSION] ⚠️  Redis connection failed: {e}")
            self.redis = None
    
    def _key(self, user_id: str, data_type: str, calculation_type: str = None) -> str:
        """
        Generate Redis key.
        
        Args:
            user_id: User identifier
            data_type: 'profile', 'conversation', 'calculations', 'transits'
            calculation_type: Specific calculation (e.g., 'd9_chart', 'dasha_data')
        """
        if calculation_type:
            return f"session:{user_id}:{data_type}:{calculation_type}"
        return f"session:{user_id}:{data_type}"
    
    # ========================================================================
    # DIVISIONAL CHART CACHE
    # ========================================================================
    
    def get_divisional_chart(self, user_id: str, chart_type: str) -> Optional[Dict]:
        """
        Get cached divisional chart.
        
        Args:
            user_id: User identifier
            chart_type: 'd1', 'd9', 'd10', etc.
            
        Returns:
            Cached chart data or None if not found
        """
        if not self.redis or chart_type not in self.DIVISIONAL_CHARTS:
            return None
        
        key = self._key(user_id, 'calculations', f'{chart_type}_chart')
        cached = self._get_json_safe(key)
        
        if cached:
            print(f"[CACHE] ✅ Using cached {chart_type.upper()} chart for {user_id}")
        else:
            print(f"[CACHE] ❌ No cached {chart_type.upper()} chart for {user_id}")
        
        return cached
    
    def store_divisional_chart(self, user_id: str, chart_type: str, chart_data: Dict) -> bool:
        """
        Store divisional chart in cache.
        
        Args:
            user_id: User identifier
            chart_type: 'd1', 'd9', 'd10', etc.
            chart_data: Chart data to store
            
        Returns:
            True if stored successfully
        """
        if not self.redis or chart_type not in self.DIVISIONAL_CHARTS:
            return False
        
        try:
            key = self._key(user_id, 'calculations', f'{chart_type}_chart')
            self.redis.setex(key, self.TTL_CALCULATIONS, json.dumps(chart_data))
            print(f"[CACHE] 💾 Stored {chart_type.upper()} chart for {user_id} (TTL: 30d)")
            return True
        except Exception as e:
            print(f"[CACHE] Error storing {chart_type} chart: {e}")
            return False
    
    def get_all_cached_charts(self, user_id: str) -> Dict[str, Dict]:
        """
        Get all cached divisional charts.
        
        Returns:
            Dictionary of {chart_type: chart_data} for all cached charts
        """
        cached_charts = {}
        
        for chart_type in self.DIVISIONAL_CHARTS:
            chart = self.get_divisional_chart(user_id, chart_type)
            if chart:
                cached_charts[chart_type] = chart
        
        return cached_charts
    
    # ========================================================================
    # DASHA DATA CACHE
    # ========================================================================
    
    def get_dasha_data(self, user_id: str) -> Optional[Dict]:
        """
        Get cached Vimshottari dasha data.
        
        Returns:
            Complete dasha data including all levels
        """
        if not self.redis:
            return None
        
        key = self._key(user_id, 'calculations', 'dasha_data')
        cached = self._get_json_safe(key)
        
        if cached:
            print(f"[CACHE] ✅ Using cached dasha data for {user_id}")
        else:
            print(f"[CACHE] ❌ No cached dasha data for {user_id}")
        
        return cached
    
    def store_dasha_data(self, user_id: str, dasha_data: Dict) -> bool:
        """
        Store complete dasha data.
        
        Expected format:
        {
            "mahadasha": {...},
            "antardasha": {...},
            "pratyantardasha": {...},
            "all_dashas": [...]  # Complete timeline
        }
        """
        if not self.redis:
            return False
        
        try:
            key = self._key(user_id, 'calculations', 'dasha_data')
            self.redis.setex(key, self.TTL_CALCULATIONS, json.dumps(dasha_data))
            print(f"[CACHE] 💾 Stored dasha data for {user_id} (TTL: 30d)")
            return True
        except Exception as e:
            print(f"[CACHE] Error storing dasha data: {e}")
            return False
    
    # ========================================================================
    # TRANSIT DATA CACHE
    # ========================================================================
    
    def get_transit_data(self, user_id: str) -> Optional[Dict]:
        """
        Get cached current transit data.
        
        Returns:
            Current transit positions (if fresh - TTL: 2h)
        """
        if not self.redis:
            return None
        
        key = self._key(user_id, 'transits', 'current')
        cached = self._get_json_safe(key)
        
        if cached:
            # Check if transit data has timestamp
            transit_time = cached.get('calculated_at')
            if transit_time:
                print(f"[CACHE] ✅ Using cached transits from {transit_time}")
            else:
                print(f"[CACHE] ✅ Using cached transits for {user_id}")
        else:
            print(f"[CACHE] ❌ No cached transit data for {user_id}")
        
        return cached
    
    def store_transit_data(self, user_id: str, transit_data: Dict) -> bool:
        """
        Store current transit data.
        
        TTL is short (2h) because transits change frequently.
        """
        if not self.redis:
            return False
        
        try:
            # Add timestamp
            transit_data['calculated_at'] = datetime.utcnow().isoformat()
            
            key = self._key(user_id, 'transits', 'current')
            self.redis.setex(key, self.TTL_TRANSITS, json.dumps(transit_data))
            print(f"[CACHE] 💾 Stored transit data for {user_id} (TTL: 2h)")
            return True
        except Exception as e:
            print(f"[CACHE] Error storing transit data: {e}")
            return False
    
    # ========================================================================
    # AYANAMSA CACHE
    # ========================================================================
    
    def get_ayanamsa(self, user_id: str) -> Optional[Dict]:
        """
        Get cached ayanamsa value.
        
        Returns:
            Ayanamsa data including value and system used
        """
        if not self.redis:
            return None
        
        key = self._key(user_id, 'calculations', 'ayanamsa')
        cached = self._get_json_safe(key)
        
        if cached:
            print(f"[CACHE] ✅ Using cached ayanamsa for {user_id}")
        else:
            print(f"[CACHE] ❌ No cached ayanamsa for {user_id}")
        
        return cached
    
    def store_ayanamsa(self, user_id: str, ayanamsa_data: Dict) -> bool:
        """
        Store ayanamsa value.
        
        Expected format:
        {
            "value": 24.123456,
            "system": "Lahiri",
            "date": "1990-07-15"
        }
        """
        if not self.redis:
            return False
        
        try:
            key = self._key(user_id, 'calculations', 'ayanamsa')
            self.redis.setex(key, self.TTL_CALCULATIONS, json.dumps(ayanamsa_data))
            print(f"[CACHE] 💾 Stored ayanamsa for {user_id} (TTL: 30d)")
            return True
        except Exception as e:
            print(f"[CACHE] Error storing ayanamsa: {e}")
            return False
    
    # ========================================================================
    # PLANET & HOUSE POSITIONS CACHE
    # ========================================================================
    
    def get_planet_positions(self, user_id: str) -> Optional[Dict]:
        """Get cached planet positions."""
        if not self.redis:
            return None
        
        key = self._key(user_id, 'calculations', 'planet_positions')
        return self._get_json_safe(key)
    
    def store_planet_positions(self, user_id: str, positions: Dict) -> bool:
        """Store planet positions."""
        if not self.redis:
            return False
        
        try:
            key = self._key(user_id, 'calculations', 'planet_positions')
            self.redis.setex(key, self.TTL_CALCULATIONS, json.dumps(positions))
            print(f"[CACHE] 💾 Stored planet positions for {user_id} (TTL: 30d)")
            return True
        except Exception as e:
            print(f"[CACHE] Error storing planet positions: {e}")
            return False
    
    def get_house_positions(self, user_id: str) -> Optional[Dict]:
        """Get cached house cusps."""
        if not self.redis:
            return None
        
        key = self._key(user_id, 'calculations', 'house_positions')
        return self._get_json_safe(key)
    
    def store_house_positions(self, user_id: str, positions: Dict) -> bool:
        """Store house cusp positions."""
        if not self.redis:
            return False
        
        try:
            key = self._key(user_id, 'calculations', 'house_positions')
            self.redis.setex(key, self.TTL_CALCULATIONS, json.dumps(positions))
            print(f"[CACHE] 💾 Stored house positions for {user_id} (TTL: 30d)")
            return True
        except Exception as e:
            print(f"[CACHE] Error storing house positions: {e}")
            return False
    
    # ========================================================================
    # COMPREHENSIVE CALCULATION STATUS
    # ========================================================================
    
    def get_calculation_status(self, user_id: str) -> CalculationCache:
        """
        Get comprehensive status of what's been calculated.
        
        Returns:
            CalculationCache object with boolean flags
        """
        status = CalculationCache()
        
        if not self.redis:
            return status
        
        # Check divisional charts
        status.has_d1_chart = self.get_divisional_chart(user_id, 'd1') is not None
        status.has_d9_chart = self.get_divisional_chart(user_id, 'd9') is not None
        status.has_d10_chart = self.get_divisional_chart(user_id, 'd10') is not None
        
        # Check other calculations
        status.has_dasha_data = self.get_dasha_data(user_id) is not None
        status.has_transit_data = self.get_transit_data(user_id) is not None
        status.has_ayanamsa = self.get_ayanamsa(user_id) is not None
        
        # Check when last calculated
        metadata_key = self._key(user_id, 'calculations', 'metadata')
        metadata = self._get_json_safe(metadata_key)
        if metadata:
            status.last_calculated = metadata.get('last_calculated')
        
        return status
    
    def update_calculation_metadata(self, user_id: str, calculation_type: str):
        """Update metadata when new calculation is performed."""
        if not self.redis:
            return
        
        try:
            metadata_key = self._key(user_id, 'calculations', 'metadata')
            metadata = self._get_json_safe(metadata_key) or {}
            
            metadata['last_calculated'] = datetime.utcnow().isoformat()
            metadata.setdefault('calculations_performed', []).append({
                'type': calculation_type,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            self.redis.setex(metadata_key, self.TTL_CALCULATIONS, json.dumps(metadata))
        except Exception as e:
            print(f"[CACHE] Error updating metadata: {e}")
    
    # ========================================================================
    # BULK OPERATIONS
    # ========================================================================
    
    def store_complete_calculation_set(
        self,
        user_id: str,
        d1_chart: Optional[Dict] = None,
        d9_chart: Optional[Dict] = None,
        d10_chart: Optional[Dict] = None,
        dasha_data: Optional[Dict] = None,
        transit_data: Optional[Dict] = None,
        ayanamsa: Optional[Dict] = None,
        planet_positions: Optional[Dict] = None,
        house_positions: Optional[Dict] = None
    ) -> Dict[str, bool]:
        """
        Store multiple calculations at once (efficient bulk operation).
        
        Returns:
            Dictionary of {calculation_type: success_boolean}
        """
        results = {}
        
        if d1_chart:
            results['d1_chart'] = self.store_divisional_chart(user_id, 'd1', d1_chart)
        
        if d9_chart:
            results['d9_chart'] = self.store_divisional_chart(user_id, 'd9', d9_chart)
        
        if d10_chart:
            results['d10_chart'] = self.store_divisional_chart(user_id, 'd10', d10_chart)
        
        if dasha_data:
            results['dasha_data'] = self.store_dasha_data(user_id, dasha_data)
        
        if transit_data:
            results['transit_data'] = self.store_transit_data(user_id, transit_data)
        
        if ayanamsa:
            results['ayanamsa'] = self.store_ayanamsa(user_id, ayanamsa)
        
        if planet_positions:
            results['planet_positions'] = self.store_planet_positions(user_id, planet_positions)
        
        if house_positions:
            results['house_positions'] = self.store_house_positions(user_id, house_positions)
        
        # Update metadata
        self.update_calculation_metadata(user_id, 'bulk_calculation')
        
        success_count = sum(results.values())
        total_count = len(results)
        print(f"[CACHE] 💾 Bulk store: {success_count}/{total_count} successful for {user_id}")
        
        return results
    
    def get_complete_calculation_set(self, user_id: str) -> Dict[str, Any]:
        """
        Get all cached calculations at once.
        
        Returns:
            Dictionary with all available calculations
        """
        return {
            'd1_chart': self.get_divisional_chart(user_id, 'd1'),
            'd9_chart': self.get_divisional_chart(user_id, 'd9'),
            'd10_chart': self.get_divisional_chart(user_id, 'd10'),
            'dasha_data': self.get_dasha_data(user_id),
            'transit_data': self.get_transit_data(user_id),
            'ayanamsa': self.get_ayanamsa(user_id),
            'planet_positions': self.get_planet_positions(user_id),
            'house_positions': self.get_house_positions(user_id),
            'calculation_status': asdict(self.get_calculation_status(user_id))
        }
    
    # ========================================================================
    # HELPER METHODS (from original session manager)
    # ========================================================================
    
    def _get_json_safe(self, key: str) -> Optional[Dict]:
        """Safely get and parse JSON data."""
        try:
            data_str = self.redis.get(key)
            return json.loads(data_str) if data_str else None
        except:
            return None
    
    def initialize_session(
        self,
        user_id: str,
        user_profile: Dict[str, Any],
        pre_calculated_data: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Initialize session (same as before, but extended with calculation cache)."""
        if not self.redis:
            return {"status": "no_cache", "message": "Redis not available"}
        
        try:
            # Store user profile
            self.redis.setex(
                self._key(user_id, "user_profile"),
                self.TTL_USER_PROFILE,
                json.dumps(user_profile)
            )
            
            # Store conversation
            conversation = conversation_history or []
            self.redis.setex(
                self._key(user_id, "conversation"),
                self.TTL_CONVERSATION,
                json.dumps(conversation)
            )
            
            # Store pre-calculated data if provided
            stored_calculations = {}
            if pre_calculated_data:
                if 'birth_chart' in pre_calculated_data or 'd1_chart' in pre_calculated_data:
                    chart = pre_calculated_data.get('birth_chart') or pre_calculated_data.get('d1_chart')
                    stored_calculations['d1_chart'] = self.store_divisional_chart(user_id, 'd1', chart)
                
                if 'd9_chart' in pre_calculated_data:
                    stored_calculations['d9_chart'] = self.store_divisional_chart(user_id, 'd9', pre_calculated_data['d9_chart'])
                
                if 'd10_chart' in pre_calculated_data:
                    stored_calculations['d10_chart'] = self.store_divisional_chart(user_id, 'd10', pre_calculated_data['d10_chart'])
                
                if 'dasha_data' in pre_calculated_data:
                    stored_calculations['dasha_data'] = self.store_dasha_data(user_id, pre_calculated_data['dasha_data'])
                
                if 'transits' in pre_calculated_data:
                    stored_calculations['transit_data'] = self.store_transit_data(user_id, pre_calculated_data['transits'])
                
                if 'ayanamsa' in pre_calculated_data:
                    stored_calculations['ayanamsa'] = self.store_ayanamsa(user_id, pre_calculated_data['ayanamsa'])
            
            # Store metadata
            metadata = {
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "calculations": stored_calculations
            }
            self.redis.setex(
                self._key(user_id, "metadata"),
                self.TTL_METADATA,
                json.dumps(metadata)
            )
            
            print(f"[SESSION] Initialized session: {user_id}")
            
            return {
                "status": "success",
                "session_id": user_id,
                "cached_calculations": stored_calculations,
                "ttl": {
                    "session": self.TTL_USER_PROFILE,
                    "calculations": self.TTL_CALCULATIONS,
                    "transits": self.TTL_TRANSITS
                }
            }
            
        except Exception as e:
            print(f"[SESSION] Error initializing session: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile."""
        return self._get_json_safe(self._key(user_id, "user_profile"))
    
    def get_conversation_history(self, user_id: str) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self._get_json_safe(self._key(user_id, "conversation")) or []
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add message to conversation history."""
        if not self.redis:
            return False
        
        try:
            conversation = self.get_conversation_history(session_id)
            
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if metadata:
                message["metadata"] = metadata
            
            conversation.append(message)
            
            # Keep last 20 messages
            if len(conversation) > 20:
                conversation = conversation[-20:]
            
            self.redis.setex(
                self._key(session_id, "conversation"),
                self.TTL_CONVERSATION,
                json.dumps(conversation)
            )
            
            return True
            
        except Exception as e:
            print(f"[SESSION] Error adding message: {e}")
            return False
    
    def session_exists(self, user_id: str) -> bool:
        """Check if session exists."""
        if not self.redis:
            return False
        return self.redis.exists(self._key(user_id, "metadata")) > 0
    
    def extend_session(self, user_id: str) -> bool:
        """Extend session TTL."""
        if not self.redis:
            return False
        
        try:
            keys_to_extend = [
                (self._key(user_id, "user_profile"), self.TTL_USER_PROFILE),
                (self._key(user_id, "conversation"), self.TTL_CONVERSATION),
                (self._key(user_id, "metadata"), self.TTL_METADATA),
            ]
            
            for key, ttl in keys_to_extend:
                if self.redis.exists(key):
                    self.redis.expire(key, ttl)
            
            return True
            
        except Exception as e:
            print(f"[SESSION] Error extending session: {e}")
            return False
    
    def clear_session(self, user_id: str, clear_calculations: bool = False) -> bool:
        """
        Clear session data.
        
        Args:
            user_id: User identifier
            clear_calculations: If True, also clear calculation cache
        """
        if not self.redis:
            return False
        
        try:
            # Always clear session data
            session_keys = [
                self._key(user_id, "user_profile"),
                self._key(user_id, "conversation"),
                self._key(user_id, "metadata"),
            ]
            
            # Optionally clear calculation cache
            if clear_calculations:
                for chart_type in self.DIVISIONAL_CHARTS:
                    session_keys.append(self._key(user_id, 'calculations', f'{chart_type}_chart'))
                
                session_keys.extend([
                    self._key(user_id, 'calculations', 'dasha_data'),
                    self._key(user_id, 'calculations', 'ayanamsa'),
                    self._key(user_id, 'calculations', 'planet_positions'),
                    self._key(user_id, 'calculations', 'house_positions'),
                    self._key(user_id, 'calculations', 'metadata'),
                    self._key(user_id, 'transits', 'current'),
                ])
            
            self.redis.delete(*session_keys)
            print(f"[SESSION] Cleared session: {user_id} (calculations: {clear_calculations})")
            return True
            
        except Exception as e:
            print(f"[SESSION] Error clearing session: {e}")
            return False
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        if not self.redis:
            return 0
        
        try:
            keys = self.redis.keys("session:*:metadata")
            return len(keys)
        except:
            return 0


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_enhanced_session_manager = None


def get_enhanced_session_manager(**redis_kwargs) -> EnhancedRedisSessionManager:
    """Get global enhanced session manager instance."""
    global _enhanced_session_manager
    
    if _enhanced_session_manager is None:
        _enhanced_session_manager = EnhancedRedisSessionManager(**redis_kwargs)
    
    return _enhanced_session_manager