<html>
  <head>
      <title>Form Example</title>
      <link href="/remote.css" rel="stylesheet" />
      <link href="/custom.css" rel="stylesheet" />
% if refresh and action=="STOP":
    <meta http-equiv="refresh" content="{{refresh*60}}">
% end
    <script src="//ajax.googleapis.com/ajax/libs/jquery/1.8.2/jquery.min.js"></script>
    <script src="//code.jquery.com/ui/1.12.1/jquery-ui.min.js"></script>

    <script type="text/javascript">
        $(document).ready(function() {
            $('.autocomplete').autocomplete({
                delay:500,
                maxResults: 10,
                source: function(request, response) {
                    $this = $(this.element);
                    $.ajax({
                        type : 'POST',
                        url: '/query_category',
                        data: {'service': $this.attr('data-service'), 'category': request.term},
                        success: function(data) {response(data)}
                    });
                }
            });

        });

        $(document).ready(function() {
            $('.blur').blur(function() {
                $(this).closest("form").submit();
            });
        });

        $(document).ready(function() {
            $('.update').submit(function(e) {
                $.ajax({
                    type: 'POST',
                    url: '/update_title',
                    data: $(this).serialize(),
                    success: function(response) {
                        for (service in response) {
                            $('.' +  service + '_title').val(response[service]['title']);
                            $('.' +  service + '_category').val(response[service]['category']);
                        }
                        $('#footer')[0].reset();
                    }
                });
                e.preventDefault();
            });
        });
  </script>
  </head>
  <body class="{{!"started" if action == "STOP" else "stopped"}}">
  <!--<input class="refresh" type="button" value="🔃" onclick="history.go(0)" /> -->
  <div id="content">
    % if services:
    <ul class="streams">
    % for service, stream in services.items():
    % if stream['enabled']:
        <li class="{{!"online" if stream['infos']['online'] else "offline"}}"><span class='service_name' style="background-image:url('/images/{{service}}.png')"></span>    <span class='viewers'>{{stream['infos']['viewers']}}</span>
    <form method="POST" class="service update" action="/">
        <input name="service" type="hidden" value="{{service}}" />
        <input name="category" data-service="{{service}}" type="text" value="{{stream['infos']['category']}}" class="{{service}}_category autocomplete blur" /><br />
        <input name="title" type="text" value="{{stream['infos']['title']}}" class="{{service}}_title blur" />
        <input type="submit" value="Submit" hidden />
    </form>
        </li>
    % end
    % end
    </ul>
    % else:
    <p>Welcome to the Stream Manager, it can update your stream title and category automatically depending on which software is running on the foreground and has the focus.<br/>>You can also use it as a resource saver as it can save CPU and networks ressources by automatically pausing processes and services.</p>
    <hr/>
    <p>No stream service has been activated, go into <strong>View > Preferences > Streams</strong> and activate some to be able to automatically check processes.</p>
    <p>You then have to press the <strong>START</strong> button below to begin checking the foreground processes. Don't forget to add your programs in the "Games" tab.</p>
    % end

    <form method="POST" class="perspective" action="/">
        <button class="action btn btn-8 btn-8f" type='submit' name='action' value='{{action}}'>{{action}}</button>
    </form>
    </div>


    <form method="POST" id="footer" class="update" action="/update_title" title="Change all streams at once, disable the automatic checks if you use different programs and want to keep your modifications" {{!'style="display:none"' if len(services) < 2 else ''}}>
        <input name="category" type="text" value="" placeholder="Category"/>
        <input name="title" type="text" value="" placeholder="Title" />
        <input type="submit" value="Submit" /><br/>
    </form>

    {{infos if defined('infos') else ''}}

  </body>
</html>
<script>
    if (window.history.replaceState) {
        window.history.replaceState(null, null, window.location.href);
    }
</script>