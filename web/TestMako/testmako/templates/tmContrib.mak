<%inherit file="tmBase.mak"/>


<%block name="blkHead">
<!-- tmContrib.blkHead: overrides tmBase.mak: blkHead -->
<script language="javascript" type="text/javascript">
function setInitialFocus() {
}
</script>

<style>
  span.example {
    font-family: Arial, Helvetica;
    font-style: bold;
    font-size: 150%;
    color: #006000;
  }

  input.here {
    background-color: #00ff00;
  }
  input.there {
    background-color: #ffffff;
  }
</style>
</%block>


<!-- tmContrib.body: start -->

  % if len(errMsg) == 0:
    <div id="body">
    <table style="border:2px solid #00ff00; margin-left:0;
      margin-right: auto;">

      <tr>
      % for col in showCols:
        <th style="border:1px solid blue; background-color:yellow">
        ${col}
        </th>
      % endfor
      </tr>
      % for row in showRows:
        <tr>
        % for col in showCols:
          <td style="border-left:3px solid white; border-right:3px solid white">
          ##% if loop.index == 0:
          ##  <a href="detail?midentspec=${row[loop.index]}">
          ##% endif

          ${row[loop.index]}

          % if loop.index == 0:
            </a>
          % endif
          </td>
        % endfor
        </tr>
      % endfor
    </table>
    </div>
  % endif

<!-- tmContrib.body: end -->
