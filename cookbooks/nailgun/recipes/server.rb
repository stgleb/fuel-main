node.set[:django][:venv] = node.nailgun.venv
include_recipe 'django'

# FIXME
# it is nice to encapsulate all these components into os package
# installing deps, creating system user, installing nailgun files

include_recipe 'nailgun::deps'

group node.nailgun.group do
  action :create
end

user node.nailgun.user do
  home node.nailgun.root
  gid node.nailgun.group
  system true
end

file "#{node[:nailgun][:root]}/nailgun/venv.py" do
  content "VENV = '#{node[:nailgun][:venv]}/local/lib/python2.7/site-packages'
"
  owner node.nailgun.user
  group node.nailgun.group
  mode 644
end

# it is assumed that nailgun files already installed into nailgun.root
execute 'chown nailgun root' do
  command "chown -R #{node[:nailgun][:user]}:#{node[:nailgun][:group]} #{node[:nailgun][:root]}"
end

execute 'chmod nailgun root' do
  command "chmod -R u+w #{node[:nailgun][:root]}"
end

execute 'Preseed Nailgun database' do
  command "#{node[:nailgun][:python]} manage.py loaddata nailgun/fixtures/default_env.json"
  cwd node.nailgun.root
  user node.nailgun.user
  action :nothing
end

execute 'Sync Nailgun database' do
  command "#{node[:nailgun][:python]} manage.py syncdb --noinput"
  cwd node.nailgun.root
  user node.nailgun.user
  notifies :run, resources('execute[Preseed Nailgun database]')
  not_if "test -e #{node[:nailgun][:root]}/nailgun.sqlite"
end

execute 'Sync Nailgun database2' do
  command "echo #{node[:nailgun][:python]} manage.py syncdb --noinput > /root/2"
  not_if "test -e #{node[:nailgun][:root]}/nailgun.sqlite"
end

execute 'Sync Nailgun database3' do
  command "echo #{node[:nailgun][:python]} manage.py syncdb --noinput > /root/3"
end


redis_instance 'nailgun'

celery_instance 'nailgun-jobserver' do
  command "#{node[:nailgun][:python]} manage.py celeryd_multi"
  cwd node.nailgun.root
  events true
  user node.nailgun.user
  virtualenv node.nailgun.venv
end

web_app 'nailgun' do
  template 'apache2-site.conf.erb'
end

