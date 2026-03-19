"""
Teams Configuration Loader.

Loads team configuration from times.json and provides helper functions.
"""

import json
import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class TeamMember:
    """Represents a team member."""
    nome: str
    funcao: str


@dataclass
class Team:
    """Represents a team."""
    time: str
    tech_leader: str
    membros: List[TeamMember] = field(default_factory=list)
    
    @property
    def member_names(self) -> List[str]:
        """Get list of member names."""
        return [m.nome for m in self.membros]
    
    @property
    def all_names(self) -> List[str]:
        """Get all names including tech leader."""
        names = [self.tech_leader] + self.member_names
        return names


def load_teams(config_path: str = None) -> List[Team]:
    """
    Load teams from JSON configuration file.
    
    Args:
        config_path: Path to times.json. If None, uses default path.
        
    Returns:
        List of Team objects.
    """
    if config_path is None:
        # Default path relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "times.json")
    
    if not os.path.exists(config_path):
        return []
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        teams = []
        for item in data:
            membros = [
                TeamMember(nome=m["nome"], funcao=m["funcao"])
                for m in item.get("membros", [])
            ]
            team = Team(
                time=item.get("time", ""),
                tech_leader=item.get("techLeader", ""),
                membros=membros
            )
            teams.append(team)
        
        return teams
    except Exception:
        return []


def get_team_names(teams: List[Team]) -> List[str]:
    """Get unique team names."""
    seen = set()
    names = []
    for team in teams:
        if team.time not in seen:
            seen.add(team.time)
            names.append(team.time)
    return names


def get_team_members_by_name(teams: List[Team], team_name: str) -> List[str]:
    """Get all member names for a specific team."""
    members = []
    for team in teams:
        if team.time == team_name:
            members.extend(team.all_names)
    return list(set(members))


def get_all_member_names(teams: List[Team]) -> List[str]:
    """Get all member names from all teams."""
    members = []
    for team in teams:
        members.extend(team.all_names)
    return list(set(members))


def find_team_for_member(teams: List[Team], member_name: str) -> Optional[str]:
    """Find which team a member belongs to."""
    member_lower = member_name.lower()
    for team in teams:
        for name in team.all_names:
            if name.lower() == member_lower or member_lower in name.lower() or name.lower() in member_lower:
                return team.time
    return None


def save_teams(teams: List[Team], config_path: str = None) -> bool:
    """
    Save teams to JSON configuration file.
    
    Args:
        teams: List of Team objects to save.
        config_path: Path to times.json. If None, uses default path.
        
    Returns:
        True if successful, False otherwise.
    """
    if config_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "times.json")
    
    try:
        data = []
        for team in teams:
            item = {
                "time": team.time,
                "techLeader": team.tech_leader,
                "membros": [
                    {"nome": m.nome, "funcao": m.funcao}
                    for m in team.membros
                ]
            }
            data.append(item)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception:
        return False
