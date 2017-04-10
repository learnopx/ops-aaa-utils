# -*- coding: utf-8 -*-
# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
##########################################################################

"""
OpenSwitch Test for RADIUS Authentication.
"""

import time
import datetime
from pytest import mark
import pexpect

TOPOLOGY = """
# +--------+         +--------+
# |        |eth0     |        |
# |  hs2   +---------+  ops1  |
# |        |     eth1|        |
# +--------+         +-+------+
#                      |eth0
#                      |
#                      |eth0
#                  +---+----+
#                  |        |
#                  |  hs1   |
#                  |        |
#                  +--------+

# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=oobmhost image="openswitch/freeradius:latest" name="Host 1"] hs1
[type=oobmhost image="openswitch/freeradius:latest" name="Host 2"] hs2

# Ports
[force_name=oobm] ops1:eth1
[force_name=oobm] ops1:eth0

# Links
ops1:eth0 -- hs1:eth0
ops1:eth1 -- hs2:eth0
"""


ssh_cmd = "ssh -F /dev/null -o StrictHostKeyChecking=no"

switches = []
hosts = []
USER_1 = "test_user1"
USER_1_PASSWD = "test_user1"
USER_NETOP = "netop"
USER_NETOP_PASSWD = "netop"
USER_NEW = "user_chap"
USER_NEW_PASSWD = "user_chap_passwd"
USER_NEW_DIFF_PASSWD = "chap_auth_diff_passwd"
USER_DUMMY = "dummyunknown"
USER_DUMMY_PASSWD = "dummypasswd"
DUMMY = "dummy"
SSH_NEWKEY_HELP_STR = "Are you sure you want to continue connecting"
LOCAL_AUTH = "local"
REMOTE_AUTH = "remote"
RADIUS_TIMEOUT = "timeout"
RADIUS_TIMEOUT_VAL = "5"
TIMEOUT_DEFAULT_VAL = 5
RADIUS_RETRIES = "retries"
RADIUS_RETRIES_TEST = "2"
RETRIES_TEST_VAL = 2
RADIUS_RETRIES_VAL = "1"
RETRIES_DEFAULT_VAL = 1
RADIUS_TIMEOUT_TEST = "10"
TIMEOUT_TEST_SEC = 10
RADIUS_PASSKEY = "key"
RADIUS_PASSKEY_VALUE = "testing123-1"
IPV6_OPS = "2013:cdba:1002:1304:4001:2005:3257:1000/64"
IPV6_OPS_SSH = "2013:cdba:1002:1304:4001:2005:3257:1000"
IPV6_HOST1 = "2013:cdba:1002:1304:4001:2005:3257:2000/64"
IPV6_HOST2 = "2013:cdba:1002:1304:4001:2005:3257:3000/64"

def stop_radius_service(step, host_idx):
    h = hosts[host_idx]
    host_ip = get_host_ip(step, host_idx)
    step("#### stop freeradius daemon for server " + host_ip + " ####")
    out = h("service freeradius stop")
    assert ("Stopping FreeRADIUS daemon freeradius") in out, "Failed to stop freeradius on host " + host_ip

def start_radius_service(step, host_idx):
    h = hosts[host_idx]
    host_ip = get_host_ip(step, host_idx)
    step("#### start freeradius daemon for server " + host_ip + " ####")
    out = h("service freeradius start")
    assert ("Starting FreeRADIUS daemon freeradius") in out, "Failed to start freeradius on host " + host_ip

def create_new_user(step, new_user, new_pass, auth_type, priv_lvl, host_idx):
    step("#### create new user ####")
    h = hosts[host_idx]
    default_conf = "/etc/freeradius/users"
    new_conf = default_conf + '.' + new_user
    content = "\n" + new_user + " Cleartext-Password := \"" + new_pass + "\"\n" + \
              "      Service-Type = " + priv_lvl
    h("echo $\'" + content + "\' > " + new_conf)
    out = h("cat " + new_conf + " >> " + default_conf)
    assert ("No such file or directory") not in out, \
            "Failed to add new user " + new_user + " to user file"

def add_new_client(step, host_idx):
    step("#### add client to radius server ####")
    h = hosts[host_idx]
    switch_ip = get_switch_ip(step)
    default_conf = "/etc/freeradius/clients.conf"
    new_client = "new_client"
    content = "\nclient " + switch_ip + " {\n" + "      ipaddr        = " + switch_ip + \
              "\n      secret        = " + RADIUS_PASSKEY_VALUE + "\n}"
    h("echo $\'" + content + "\' > " + new_client)
    out = h("cat " + new_client + " >> " + default_conf)
    assert ("No such file or directory") not in out, \
            "Failed to add new client " + switch_ip + " to client file"

def print_freeradius_conf(step, host_idx):
    step("#### print clients.conf content ####")
    h = hosts[host_idx]
    out = h("tail -10 /etc/freeradius/clients.conf")
    print(out)
    step("#### print users content ####")
    out = h("tail -10 /etc/freeradius/users")
    print(out)

def init_radius_server(step):
    """ This function is to setup RADIUS server
    """
    step("####### Configure RADIUS servers start #######")
    stop_radius_service(step, 0)
    stop_radius_service(step, 1)
    switch_ip = get_switch_ip(step)
    add_new_client(step, 0)
    add_new_client(step, 1)
    h1 = hosts[0]
    h1("sed -i \"196s/192.168.0.0/"+switch_ip+"/\" "
        "/etc/freeradius/clients.conf")
    h1("sed -i \"196,199s/#//\" /etc/freeradius/clients.conf")
    h2 = hosts[1]
    h2("sed -i \"196s/192.168.0.0/"+switch_ip+"/\" "
       "/etc/freeradius/clients.conf")
    h2("sed -i \"196,199s/#//\" /etc/freeradius/clients.conf")
    create_new_user(step, USER_1, USER_1_PASSWD, 'pap', 'Nas-Prompt-User', 0)
    create_new_user(step, USER_1, USER_1_PASSWD, 'pap', 'Nas-Prompt-User', 1)
    create_new_user(step, USER_NEW, USER_NEW_PASSWD, 'chap', 'Nas-Prompt-User', 1)
    start_radius_service(step, 0)
    start_radius_service(step, 1)
    print_freeradius_conf(step, 1)
    step("####### Configure RADIUS servers succeed #######")

def setup_radius_server_ipv6(step):
    """ This function is to setup RADIUS server with IPv6 address
    """
    step("####### Configure RADIUS servers start #######")
    set_host_ipv6(step, 0, IPV6_HOST1)
    set_host_ipv6(step, 1, IPV6_HOST2)
    print_freeradius_conf(step, 1)
    step("####### Configure RADIUS servers succeed #######")

def setup_radius_client(step):
    """ This function is to setup RADIUS client in the switch
    """
    step("####### Configure RADIUS client (on OpenSwitch) start #######")
    s1 = switches[0]
    host_1_ip_address = get_host_ip(step, 0)
    host_2_ip_address = get_host_ip(step, 1)
    print("RADIUS Server:" + host_1_ip_address)
    print("RADIUS Server:" + host_2_ip_address)
    setup_global_default(step, RADIUS_PASSKEY, RADIUS_PASSKEY_VALUE)
    out = s1("configure terminal")
    assert "Unknown command" not in out, \
        "Failed to enter configuration terminal"
    s1("radius-server host " + host_1_ip_address)
    s1("radius-server host " + host_2_ip_address + " key testing123-1 auth-type chap")
    s1("aaa group server radius sg1")
    s1("server " + host_1_ip_address)
    s1("exit")
    s1("aaa group server radius sg2")
    s1("server " + host_2_ip_address)
    s1("end")
    out = s1("show running-config")
    assert ("sg1" in out) and ("sg2" in out), \
        "Failed to create server groups"
    step("####### Configure RADIUS client (on OpenSwitch) succeed #######")

def update_radius_client(step):
    """ This function is to setup RADIUS client in the switch
    """
    step("####### Configure RADIUS client (on OpenSwitch) start #######")
    s1 = switches[0]
    set_switch_ipv6_test(step)
    old_ip_1 = get_host_ip(step, 0)
    old_ip_2 = get_host_ip(step, 1)
    host_1_ipv6_address = get_host_ipv6(step, 0)
    host_2_ipv6_address = get_host_ipv6(step, 1)
    print("RADIUS Server:" + host_1_ipv6_address)
    print("RADIUS Server:" + host_2_ipv6_address)
    setup_global_default(step, RADIUS_PASSKEY, RADIUS_PASSKEY_VALUE)
    out = s1("configure terminal")
    assert "Unknown command" not in out, \
        "Failed to enter configuration terminal"
    s1("radius-server host " + host_1_ipv6_address)
    s1("radius-server host " + host_2_ipv6_address + " key tac_test auth-type chap")
    s1("aaa group server radius+ sg1")
    s1("no server " + old_ip_1)
    s1("server " + host_1_ipv6_address)
    s1("exit")
    s1("aaa group server radius+ sg2")
    s1("no server " + old_ip_2)
    s1("server " + host_2_ipv6_address)
    s1("end")
    out = s1("show running-config")
    assert ("sg1" in out) and ("sg2" in out), \
        "Failed to create server groups"
    step("####### Configure RADIUS client (on OpenSwitch) succeed #######")


def setup_global_default(step, name, value):
    """ This function is to setup RADIUS default values
    """
    step("###### Configure RADIUS client global " + name + " start #######")
    s1 = switches[0]
    out = s1("configure terminal")
    assert "Unknown command" not in out, \
        "Failed to enter configuration terminal"
    config = "radius-server " + name + " " + value
    s1(config)
    s1("exit")
    out = s1("show radius-server")
    assert (value in out), "Failed to configure global value"
    step("###### Configure RADIUS client global " + name + " succeed #######")

def show_switch_config(step):
    s1 = switches[0]
    step("#### Running configuration ####")
    run = s1("show running-config")
    print(run)

def show_radius_log(step, host_idx):
    h = hosts[host_idx]
    step("#### freeradius log ####")
    c = h("tail -1 /var/log/freeradius/radius.log")
    print(c)


def verify_login_success(step, user, passwd, login_type, is_ipv6):
    switch_ip = get_switch_ip(step)
    if is_ipv6:
        switch_ip = IPV6_OPS_SSH
    s1 = switches[0]
    hs = hosts[1]
    my_ssh = ssh_cmd + " " + user + "@" + switch_ip
    matches = ['password:']
    bash_shell = hs.get_shell('bash')
    assert bash_shell.send_command(my_ssh, matches) is 0, "Failed with" \
        " SSH command."
    matches = ['#']
    assert bash_shell.send_command(passwd, matches) is 0, "Failed SSH" \
        " login."
    bash_shell.send_command("exit")
    step("#### passed SSH login with " + login_type + " credenticals ####")


def verify_login_failure(step, user, passwd, login_type):
    switch_ip = get_switch_ip(step)
    s1 = switches[0]
    hs = hosts[1]
    my_ssh = ssh_cmd + " " + user + "@" + switch_ip
    matches = ['password:']
    bash_shell = hs.get_shell('bash')
    assert bash_shell.send_command(my_ssh, matches) is 0, "Failed with" \
        " SSH command."
    assert bash_shell.send_command(passwd, matches) is 0, "Failed to" \
        " block unauthorized SSH login."
    assert bash_shell.send_command(passwd, matches) is 0, "Failed to" \
        " block unauthorized SSH login."
    matches = ['Permission denied']
    assert bash_shell.send_command(passwd, matches) is 0, "Failed to" \
        " block unauthorized SSH login."
    step("#### blocked SSH login with " + login_type + " credenticals ####")


def verify_login_success_2nd_attempt(step, user, passwd, login_type):
    switch_ip = get_switch_ip(step)
    s1 = switches[0]
    hs = hosts[1]
    my_ssh = ssh_cmd + " " + user + "@" + switch_ip
    matches = ['password:']
    bash_shell = hs.get_shell('bash')
    assert bash_shell.send_command(my_ssh, matches) is 0, "Failed with" \
        " SSH command."
    assert bash_shell.send_command(DUMMY, matches) is 0, "Failed to" \
        " block unauthorized SSH login."
    matches = ['#']
    assert bash_shell.send_command(passwd, matches) is 0, "Failed SSH" \
        " login."
    bash_shell.send_command("exit")
    step("#### passed SSH login with " + login_type + " credenticals 2nd attempt ####")


def verify_login_failure_timeout_then_success_2nd_attempt(step, user, passwd):
    switch_ip = get_switch_ip(step)
    s1 = switches[0]
    hs = hosts[1]
    my_ssh = ssh_cmd + " " + user + "@" + switch_ip
    matches = ['password:']
    bash_shell = hs.get_shell('bash')
    stop_radius_service(step, 0)
    assert bash_shell.send_command(my_ssh, matches) is 0, "Failed with" \
        " SSH command."
    t1 = time.time()
    bash_shell.send_command(passwd, matches)
    t2 = time.time()
    diff=(datetime.datetime.fromtimestamp(t1) - datetime.datetime.fromtimestamp(t2))
    seconds = abs(diff.total_seconds())
    test_sec = TIMEOUT_TEST_SEC * (RETRIES_DEFAULT_VAL + 1)
    assert seconds >= test_sec and seconds <= (test_sec + 1), "#### Failed timeout testcase! ####"
    start_radius_service(step, 0)
    matches = ['#']
    assert bash_shell.send_command(passwd, matches) is 0, "Failed SSH" \
        " login."
    bash_shell.send_command("exit")
    step("#### passed login success 2nd attempt with timeout = 10 and after server reboot  ####")


def verify_login_success_2nd_attempt_retry(step, user, passwd, login_type):
    switch_ip = get_switch_ip(step)
    s1 = switches[0]
    hs = hosts[1]
    my_ssh = ssh_cmd + " " + user + "@" + switch_ip
    matches = ['password:']
    bash_shell = hs.get_shell('bash')
    stop_radius_service(step, 0)
    assert bash_shell.send_command(my_ssh, matches) is 0, "Failed with" \
        " SSH command."
    t1 = time.time()
    bash_shell.send_command(passwd, matches)
    t2 = time.time()
    diff=(datetime.datetime.fromtimestamp(t1) - datetime.datetime.fromtimestamp(t2))
    seconds = abs(diff.total_seconds())
    test_sec = TIMEOUT_DEFAULT_VAL * (RETRIES_TEST_VAL + 1)
    assert seconds >= test_sec and seconds <= (test_sec + 1), "#### Failed retries testcase! ####"
    start_radius_service(step, 0)
    matches = ['#']
    assert bash_shell.send_command(passwd, matches) is 0, "Failed SSH" \
        " login."
    bash_shell.send_command("exit")
    step("#### passed SSH login with " + login_type + " credenticals 2nd attempt ####")


def get_switch_ip(step):
    """ This function is to get switch IP addess
    """
    s1 = switches[0]
    out = s1("ifconfig eth0", shell="bash")
    switch_ip = out.split("\n")[1].split()[1][5:]
    return switch_ip

def get_host_ip(step, host_id):
    """ This function is to get host IP addess
    """
    host = hosts[host_id]
    out = host("ifconfig %s" % host.ports["eth0"])
    host_ip_address = out.split("\n")[1].split()[1][5:]
    return host_ip_address

def set_switch_ipv6_test(step):
    """ This function is to set switch IPv6 address
    """
    ops1 = switches[0]
    with ops1.libs.vtysh.ConfigInterfaceMgmt() as ctx:
        ctx.ip_static(IPV6_OPS)

def set_switch_ipv6_mid(step):
    """ This function is to set host IPv6 address
    """
    ops1 = switches[0]
    ops1.libs.ip.interface('eth0', addr=IPV6_OPS, up=True)
    out = ops1("ifconfig %s" % ops1.ports["eth0"])
    assert IPV6_OPS in out,\
        "Failed to configure IPv6 address"


def set_switch_ipv6(step):
    """ This function is to set host IPv6 address
    """
    ops1 = switches[0]
    cmd = 'ip addr add ' + IPV6_OPS + ' dev eth0'
    ops1(cmd, shell='bash')
    out = ops1('ifconfig eth0', shell='bash')
    assert IPV6_OPS in out,\
        "Failed to configure IPv6 address"

def set_host_ipv6(step, host_id, address):
    """ This function is to set host IPv6 address
    """
    host = hosts[host_id]
    host.libs.ip.interface('eth0', addr=address, up=True)
    out = host("ifconfig %s" % host.ports["eth0"])
    assert address in out,\
        "Failed to configure IPv6 address"

def get_host_ipv6(step, host_id):
    """ This function is to set host IPv6 address
    """
    host = hosts[host_id]
    out = host("ifconfig %s" % host.ports["eth0"])
    host_ipv6_address = out.split("\n")[3].split()[2]
    return host_ipv6_address

def enable_fail_through(step):
    """ This function is to enable fail through
    with CLI command"""
    step("###### Enable fail through  ######")
    s1 = switches[0]
    out = s1("configure terminal")
    assert "Unknown command" not in out, \
        "Failed to enter configuration terminal"
    out = s1("aaa authentication allow-fail-through")
    assert "Unknown command" not in out, \
        "Failed to enable aaa authentication allow-fail-through"
    s1("exit")
    out = s1("show running-config")
    assert "aaa authentication allow-fail-through" in out, \
        "Failed to enable fail through"

def disable_fail_through(step):
    """ This function is to disable fail through
    with CLI command"""
    step("###### Disable fail through  ######")
    s1 = switches[0]
    out = s1("configure terminal")
    assert "Unknown command" not in out, \
        "Failed to enter configuration terminal"
    out = s1("no aaa authentication allow-fail-through")
    assert "Unknown command" not in out, \
        "Failed to enable aaa authentication allow-fail-through"
    s1("exit")
    out = s1("show running-config")
    assert "aaa authentication allow-fail-through" not in out, \
        "Failed to disable fail through"

def enable_local_authentication(step):
    """ This function is to enable local authentication in DB
    with CLI command"""
    step("###### Configure local authentication  ######")
    s1 = switches[0]
    out = s1("configure terminal")
    assert "Unknown command" not in out, \
        "Failed to enter configuration terminal"
    s1("aaa authentication login default local")
    s1("exit")
    out = s1("show running-config")
    assert "aaa authentication login default local" in out, \
        "Failed to configure aaa authentication local"

def enable_radius_authentication_by_group(step, group_list):
    """ This function is to enable RADIUS authentication in DB
    with CLI command"""
    step("###### Configure RADIUS authentication by group ######")
    s1 = switches[0]
    out = s1("configure terminal")
    assert "Unknown command" not in out, \
        "Failed to enter configuration terminal"
    cmd = "aaa authentication login default group"
    for group_name in group_list:
        cmd = cmd + " " + group_name
    s1(cmd)
    s1("exit")

    out = s1("show running-config")
    assert cmd in out, \
        "Failed to configure " + cmd

def disable_authentication_by_group(step):
    """ This function is to disable group authentication in DB
    with CLI command"""
    step("###### Configure authentication disable (default local authentication)  ######")
    s1 = switches[0]
    out = s1("configure terminal")
    assert "Unknown command" not in out, \
        "Failed to enter configuration terminal"

    s1("no aaa authentication login default")
    s1("exit")

    out = s1("show running-config")
    assert "aaa authentication login default" not in out, \
        "Failed to disable aaa authentication"

def login_ssh_local(step):
    """This function is to verify local authentication functionality
     """
    is_ipv6 = False
    step("####### Test SSH login with local authenication start #######")
    step("#### verify login success with local user (default) ####")
    show_switch_config(step)
    verify_login_success(step, USER_NETOP, USER_NETOP_PASSWD, LOCAL_AUTH, is_ipv6)
    enable_local_authentication(step)
    show_switch_config(step)
    step("#### verify login success with local user ####")
    verify_login_success(step, USER_NETOP, USER_NETOP_PASSWD, LOCAL_AUTH, is_ipv6)
    step("#### verify login failure with incorrect password ####")
    verify_login_failure(step, USER_NETOP, DUMMY, LOCAL_AUTH)
    step("#### verify login failure with non-exist user ####")
    verify_login_failure(step, USER_DUMMY, USER_DUMMY_PASSWD, LOCAL_AUTH)
    step("####### Test SSH login with local authenication succeed #######")

def login_ssh_radius(step, is_user_group):
    """This function is to verify RADIUS authentication functionality
    """
    is_ipv6 = False
    step("####### Test SSH login with RADIUS authentication start #######")
    show_switch_config(step)
    step("#### verify login success with remote user ####")
    verify_login_success(step, USER_1, USER_1_PASSWD, REMOTE_AUTH, is_ipv6)
    show_radius_log(step, 0)
    step("#### verify login failure with incorrect password ####")
    verify_login_failure(step, USER_1, DUMMY, REMOTE_AUTH)
    show_radius_log(step, 0)
    step("#### verify login failure with non-exist user ####")
    verify_login_failure(step, USER_DUMMY, USER_DUMMY_PASSWD, REMOTE_AUTH)
    show_radius_log(step, 0)
    step("#### verify login success with second password attempt ####")
    verify_login_success_2nd_attempt(step, USER_1, USER_1_PASSWD, REMOTE_AUTH)
    show_radius_log(step, 0)
    if is_user_group:
        step("#### verify login failure with dummy global passkey ####")
        setup_global_default(step, RADIUS_PASSKEY, DUMMY)
        verify_login_failure(step, USER_1, USER_1_PASSWD, REMOTE_AUTH)
        setup_global_default(step, RADIUS_PASSKEY, RADIUS_PASSKEY_VALUE)
        step("#### verify login success 2nd attempt with timeout = 10, retries = 1 and after server reboot ####")
        setup_global_default(step, RADIUS_TIMEOUT, RADIUS_TIMEOUT_TEST)
        verify_login_failure_timeout_then_success_2nd_attempt(step, USER_1, USER_1_PASSWD)
        step("#### verify login success 2nd attempt with retries = 2 and after server reboot ####")
        setup_global_default(step, RADIUS_RETRIES, RADIUS_RETRIES_TEST)
        setup_global_default(step, RADIUS_TIMEOUT, RADIUS_TIMEOUT_VAL)
        verify_login_success_2nd_attempt_retry(step, USER_1, USER_1_PASSWD, REMOTE_AUTH)
        setup_global_default(step, RADIUS_RETRIES, RADIUS_RETRIES_VAL)
        show_radius_log(step, 0)
    step("####### Test SSH login with RADIUS authentication succeed #######")

def login_ssh_radius_ipv6(step):
    """This function is to verify RADIUS authentication functionality
    """
    is_ipv6 = True
    step("####### Test SSH login with RADIUS authentication start #######")
    show_switch_config(step)
    step("#### verify login success with remote user ####")
    verify_login_success(step, USER_1, USER_1_PASSWD, REMOTE_AUTH, is_ipv6)
    show_radius_log(step, 0)
    step("####### Test SSH login with RADIUS authentication succeed #######")

def login_ssh_fail_through(step):
    """This function is to verify authentication fail-through functionality
    """
    is_ipv6 = False
    step("####### Test SSH login with fail-through enable/disable start #######")
    disable_fail_through(step)
    show_switch_config(step)
    step("#### verify login failure with remote user from second priority authentication group ####")
    verify_login_failure(step, USER_NEW, USER_NEW_PASSWD, REMOTE_AUTH)
    show_radius_log(step, 0)

    enable_fail_through(step)
    show_switch_config(step)
    step("#### verify login success with remote user from second priority authentication group ####")
    verify_login_success(step, USER_NEW, USER_NEW_PASSWD, REMOTE_AUTH, is_ipv6)
    show_radius_log(step, 1)

    step("#### verify login success with local user, and local as first priority authentication group ####")
    group_list = ['local', 'sg1', 'sg2']
    enable_radius_authentication_by_group(step, group_list)
    show_switch_config(step)
    verify_login_success(step, USER_NETOP, USER_NETOP_PASSWD, LOCAL_AUTH, is_ipv6)
    step("#### verify login success with local user, and local as second priority authentication group ####")
    group_list = ['sg1', 'local', 'sg2']
    enable_radius_authentication_by_group(step, group_list)
    show_switch_config(step)
    verify_login_success(step, USER_NETOP, USER_NETOP_PASSWD, LOCAL_AUTH, is_ipv6)
    step("#### verify login success with local user, and local as last priority authentication group ####")
    group_list = ['sg1', 'sg2', 'local']
    enable_radius_authentication_by_group(step, group_list)
    show_switch_config(step)
    verify_login_success(step, USER_NETOP, USER_NETOP_PASSWD, LOCAL_AUTH, is_ipv6)
    step("####### Test SSH login with fail-through enable/disable succeed #######")

@mark.skipif(True, reason="Disabling as framework issue present")
@mark.platform_incompatible(['ostl'])
def test_aaa_ft_authentication(topology, step):
    global switches, hosts
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert ops1 is not None
    assert hs1 is not None
    assert hs2 is not None

    switches = [ops1]
    hosts = [hs1, hs2]

    ops1.name = "ops1"
    hs1.name = "hs1"
    hs2.name = "hs2"

    is_user_group = False

    init_radius_server(step)
    setup_radius_client(step)

    group_list = ['radius']
    enable_radius_authentication_by_group(step, group_list)
    login_ssh_radius(step, is_user_group)

    is_user_group = True
    group_list = ['sg1']
    enable_radius_authentication_by_group(step, group_list)
    login_ssh_radius(step, is_user_group)

    group_list = ['sg1', 'sg2']
    enable_radius_authentication_by_group(step, group_list)
    login_ssh_fail_through(step)
