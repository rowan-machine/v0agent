# src/app/infrastructure/mdns.py
"""
mDNS Device Discovery - Phase 4.3

Provides local network device discovery using Zeroconf/mDNS.
Enables SignalFlow instances to find each other on the same network.

Features:
- Service registration (announce this device)
- Service discovery (find other devices)
- Device presence monitoring
- Automatic sync pairing

Usage:
    from .mdns import get_mdns_discovery
    
    discovery = get_mdns_discovery()
    
    # Start discovery
    await discovery.start()
    
    # Get discovered devices
    devices = discovery.get_devices()
    
    # Stop discovery
    await discovery.stop()
"""

import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Service type for SignalFlow devices
SERVICE_TYPE = "_signalflow._tcp.local."
SERVICE_NAME = "SignalFlow"


@dataclass
class DiscoveredDevice:
    """Represents a discovered SignalFlow device."""
    device_id: str
    device_name: str
    device_type: str  # desktop, mobile, web
    host: str
    port: int
    api_version: str = "v1"
    discovered_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    properties: Dict[str, str] = field(default_factory=dict)
    
    @property
    def url(self) -> str:
        """Get device API URL."""
        return f"http://{self.host}:{self.port}/api/{self.api_version}"


class MDNSDiscovery:
    """
    mDNS-based device discovery for local network sync.
    
    Uses Zeroconf to register this device as a SignalFlow service
    and discover other SignalFlow devices on the network.
    """
    
    _instance: Optional['MDNSDiscovery'] = None
    
    def __init__(
        self,
        device_id: str = "signalflow-default",
        device_name: str = "SignalFlow Device",
        device_type: str = "desktop",
        port: int = 8000,
    ):
        """
        Initialize mDNS discovery.
        
        Args:
            device_id: Unique identifier for this device
            device_name: Human-readable device name
            device_type: Type of device (desktop, mobile, web)
            port: Port this device's API is running on
        """
        self._device_id = device_id
        self._device_name = device_name
        self._device_type = device_type
        self._port = port
        
        self._zeroconf = None
        self._service_info = None
        self._browser = None
        self._running = False
        
        self._devices: Dict[str, DiscoveredDevice] = {}
        self._callbacks: List[Callable[[DiscoveredDevice, str], None]] = []
    
    async def start(self) -> bool:
        """
        Start mDNS discovery and service registration.
        
        Returns:
            True if started successfully
        """
        if self._running:
            return True
        
        try:
            from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
            from zeroconf.asyncio import AsyncZeroconf
            
            # Create Zeroconf instance
            self._zeroconf = AsyncZeroconf()
            
            # Get local IP
            local_ip = self._get_local_ip()
            
            # Create service info for this device
            self._service_info = ServiceInfo(
                SERVICE_TYPE,
                f"{self._device_name}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(local_ip)],
                port=self._port,
                properties={
                    "device_id": self._device_id,
                    "device_name": self._device_name,
                    "device_type": self._device_type,
                    "api_version": "v1",
                },
            )
            
            # Register service
            await self._zeroconf.async_register_service(self._service_info)
            logger.info(f"✅ Registered mDNS service: {self._device_name} at {local_ip}:{self._port}")
            
            # Start browser for other devices
            self._browser = ServiceBrowser(
                self._zeroconf.zeroconf,
                SERVICE_TYPE,
                self,
            )
            
            self._running = True
            logger.info("🔍 mDNS discovery started")
            return True
            
        except ImportError:
            logger.warning("⚠️ zeroconf not installed, mDNS discovery disabled")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to start mDNS discovery: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop mDNS discovery."""
        if not self._running:
            return
        
        try:
            if self._browser:
                self._browser.cancel()
            
            if self._service_info and self._zeroconf:
                await self._zeroconf.async_unregister_service(self._service_info)
            
            if self._zeroconf:
                await self._zeroconf.async_close()
            
            self._running = False
            logger.info("🛑 mDNS discovery stopped")
        except Exception as e:
            logger.error(f"Error stopping mDNS: {e}")
    
    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            # Connect to external address to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    # ServiceListener callbacks for Zeroconf
    def add_service(self, zc, service_type: str, name: str) -> None:
        """Called when a service is discovered."""
        asyncio.create_task(self._handle_service_added(zc, service_type, name))
    
    def remove_service(self, zc, service_type: str, name: str) -> None:
        """Called when a service is removed."""
        self._handle_service_removed(name)
    
    def update_service(self, zc, service_type: str, name: str) -> None:
        """Called when a service is updated."""
        asyncio.create_task(self._handle_service_added(zc, service_type, name))
    
    async def _handle_service_added(self, zc, service_type: str, name: str) -> None:
        """Process a discovered service."""
        try:
            from zeroconf import ServiceInfo
            
            info = ServiceInfo(service_type, name)
            info.request(zc, 3000)  # 3 second timeout
            
            if not info.addresses:
                return
            
            # Parse properties
            props = {
                k.decode() if isinstance(k, bytes) else k: 
                v.decode() if isinstance(v, bytes) else v
                for k, v in info.properties.items()
            }
            
            device_id = props.get("device_id", name)
            
            # Skip self
            if device_id == self._device_id:
                return
            
            device = DiscoveredDevice(
                device_id=device_id,
                device_name=props.get("device_name", name),
                device_type=props.get("device_type", "unknown"),
                host=socket.inet_ntoa(info.addresses[0]),
                port=info.port,
                api_version=props.get("api_version", "v1"),
                properties=props,
            )
            
            is_new = device_id not in self._devices
            self._devices[device_id] = device
            
            action = "discovered" if is_new else "updated"
            logger.info(f"📱 Device {action}: {device.device_name} ({device.host}:{device.port})")
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(device, action)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing discovered service: {e}")
    
    def _handle_service_removed(self, name: str) -> None:
        """Process a removed service."""
        # Find device by name
        for device_id, device in list(self._devices.items()):
            if device.device_name in name:
                del self._devices[device_id]
                logger.info(f"📴 Device removed: {device.device_name}")
                
                for callback in self._callbacks:
                    try:
                        callback(device, "removed")
                    except Exception:
                        pass
                break
    
    def get_devices(self) -> List[DiscoveredDevice]:
        """Get all discovered devices."""
        return list(self._devices.values())
    
    def get_device(self, device_id: str) -> Optional[DiscoveredDevice]:
        """Get a specific device by ID."""
        return self._devices.get(device_id)
    
    def on_device_change(self, callback: Callable[[DiscoveredDevice, str], None]) -> None:
        """
        Register callback for device changes.
        
        Args:
            callback: Function(device, action) where action is "discovered", "updated", or "removed"
        """
        self._callbacks.append(callback)
    
    @property
    def device_count(self) -> int:
        """Number of discovered devices."""
        return len(self._devices)
    
    @property
    def is_running(self) -> bool:
        """Whether discovery is running."""
        return self._running


# Singleton instance
_mdns_discovery: Optional[MDNSDiscovery] = None


def get_mdns_discovery(
    device_id: Optional[str] = None,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
    port: Optional[int] = None,
) -> MDNSDiscovery:
    """
    Get the mDNS discovery singleton.
    
    Args:
        device_id: Device ID (only used on first call)
        device_name: Device name (only used on first call)
        device_type: Device type (only used on first call)
        port: API port (only used on first call)
        
    Returns:
        MDNSDiscovery instance
    """
    global _mdns_discovery
    if _mdns_discovery is None:
        import os
        import uuid
        
        _mdns_discovery = MDNSDiscovery(
            device_id=device_id or os.environ.get("DEVICE_ID", str(uuid.uuid4())[:8]),
            device_name=device_name or os.environ.get("DEVICE_NAME", f"SignalFlow-{socket.gethostname()}"),
            device_type=device_type or os.environ.get("DEVICE_TYPE", "desktop"),
            port=port or int(os.environ.get("PORT", 8000)),
        )
    return _mdns_discovery
